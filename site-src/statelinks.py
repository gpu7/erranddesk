"""Same-state links between published city guides.

The city list in src/data/cities.json is the grouping the map already uses.
Each city page links to other guides in that same state only. Selection walks
forward from the city in slug order and wraps around, capped so the block
stays short. A cap of one or more makes the directed graph a circulant, so
every city in the state can be reached by following these links. The block is
not a nearest-city list: coordinates are not used, and the heading does not
say nearby.

The map page has no URL that opens a state zoom (zoom is a script-only
button). It does have a real id on each state's list heading, list-<state>,
and city pages link there.
"""
import html
import json
from pathlib import Path

# Other guides shown besides the map link. States with fewer cities show all
# of the others. One step would already connect the state; a short window
# keeps the hop count small without listing every city.
SIBLING_CAP = 6

_RELATED = "<h2 id=\"related\">"


def map_list_id(state_name):
    """Fragment id of that state's heading in the map page's city list."""
    return "list-" + state_name.lower().replace(" ", "-")


def load(path):
    data = json.loads(Path(path).read_text())
    return Graph(data["states"], data["cities"])


class Graph:
    def __init__(self, states, cities):
        self.states = states
        self.cities = cities
        seen = set()
        by_state = {}
        for city in cities:
            slug = city["slug"]
            if slug in seen:
                raise ValueError(f"duplicate city slug {slug}")
            if city["state"] not in states:
                raise ValueError(f"unknown state for {slug}")
            seen.add(slug)
            by_state.setdefault(city["state"], []).append(city)
        self.by_slug = {city["slug"]: city for city in cities}
        self.by_state = by_state
        counts = {}
        for city in cities:
            counts[city["name"]] = counts.get(city["name"], 0) + 1
        self.dup_names = {name for name, n in counts.items() if n > 1}
        for code, group in by_state.items():
            group.sort(key=lambda city: city["slug"])

    def siblings(self, slug, cap=SIBLING_CAP):
        """Other cities in this state. Empty when the state has only this city."""
        city = self.by_slug[slug]
        group = self.by_state[city["state"]]
        slugs = [item["slug"] for item in group]
        index = slugs.index(slug)
        count = len(group)
        take = min(cap, count - 1)
        picked = [group[(index + step) % count] for step in range(1, take + 1)]
        picked.sort(key=lambda item: (item["name"].lower(), item["slug"]))
        return picked

    def label(self, city):
        """Anchor text. A name used in more than one state keeps the state."""
        if city["name"] in self.dup_names:
            return city["name"] + ", " + self.states[city["state"]]
        return city["name"]

    def place(self, slug):
        city = self.by_slug[slug]
        return city["name"] + ", " + self.states[city["state"]]

    def nav_html(self, slug):
        """Static nav inserted on the city page. data-search-skip keeps it out of the index."""
        city = self.by_slug[slug]
        state_name = self.states[city["state"]]
        heading_id = "more-in-" + map_list_id(state_name)[len("list-"):]
        lines = [
            f'<nav class="more-in-state" aria-labelledby="{heading_id}" data-search-skip>',
            f'<h2 id="{heading_id}">More in {html.escape(state_name)}</h2>',
        ]
        siblings = self.siblings(slug)
        if siblings:
            lines.append("<ul>")
            for other in siblings:
                href = "/" + other["slug"] + "/"
                text = html.escape(self.label(other))
                lines.append(f'<li><a href="{href}">{text}</a></li>')
            lines.append("</ul>")
        fragment = map_list_id(state_name)
        lines.append(
            f'<p class="small"><a href="/map/#{fragment}">{html.escape(state_name)} on the city guides map</a></p>'
        )
        lines.append("</nav>")
        return "\n".join(lines) + "\n\n"

    def inject(self, path, body):
        """Insert the nav on a city guide, just before its existing related-guides list.

        path is the builder's URL path, such as "denver/" or "guides/fax-prices/".
        Pages that are not city guides are returned unchanged.
        """
        if not path or "/" in path.strip("/"):
            return body
        slug = path.strip("/")
        if slug not in self.by_slug:
            return body
        marker = "City guide · " + self.place(slug)
        if marker not in body:
            raise SystemExit(f"{slug} is in the city list but the page does not say {marker!r}")
        if body.count(_RELATED) != 1:
            raise SystemExit(f"{slug} should have one related-guides heading to attach the state links")
        return body.replace(_RELATED, self.nav_html(slug) + _RELATED, 1)
