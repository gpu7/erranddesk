# Errand Desk: AWS launch checklist (Richard does each step in the AWS console)

Region rule: S3 bucket and ACM certificate both go in **US East (N. Virginia) us-east-1**. CloudFront requires the certificate there.
💲 marks a step that costs money. Everything else is $0 at our size. Prices checked Oct 21, 2026.
Files are in `/workspace/mogul/deploy/`: `site/` (upload this), `s3-bucket-policy.json`, `cloudfront-function-index-rewrite.js`, `upload-commands.sh` (optional CLI).

**Before you start, check eligibility.** AWS's flat-rate plan doc says accounts are **not eligible** for flat-rate plans while "Your account is using AWS Free Tier." In **Billing and Cost Management → Free Tier** (or the account plan page), check whether the account is on the AWS Free Tier "free plan." If it is, either upgrade the account to a paid plan first, or skip the flat-rate plan in step 10 and use pay-as-you-go (estimated about $0.50/month, mostly the hosted zone).

### A. Cost safety net
1. **Billing and Cost Management → Budgets → Create budget.**
   - Choose **Customize (advanced)** → **Cost budget** → Next. Name: `erranddesk-monthly`. Period: **Monthly**. Budget renewal: **Recurring**. Budgeting method: **Fixed**. Amount: **5.00** USD. Scope: all AWS services → Next.
   - **Add alert threshold:** 80% of budgeted amount, trigger **Actual**. Email: your address.
   - **Add alert threshold:** 100% of budgeted amount, trigger **Forecasted**. Email: your address.
   - Don't add budget "actions." Next → Create budget.
   - Cost: $0. AWS says "You can monitor and receive notifications on your budgets free of charge." Only action-enabled budgets beyond the first two ($0.10/day each) and Budgets Reports ($0.01 per report) cost money. Source: https://aws.amazon.com/aws-cost-management/aws-budgets/pricing/

### B. Domain
2. 💲 **Route 53 → Domains → Registered domains → Register domains.** Search `erranddesk.com` → Select → **Proceed to checkout**.
   - Duration: **1 year**. **Auto-renew: ON.**
   - Contacts: your details. **Privacy protection: ON** (hides contact info from WHOIS; it must match across all contacts).
   - Review, accept the terms → **Submit**.
   - **Cost: $16.00/year** (Route 53 .com price from Jul 1, 2026, before fees and taxes). AWS credits can't pay for domain registration.
   - Then open **Domains → Requests** and watch for the registrant-contact **verification email**. Click its link.
3. **Hosted zone:** Route 53 creates `erranddesk.com` automatically. Confirm it under **Hosted zones**. Don't create a second one.
   - 💲 $0.50/month on pay-as-you-go, but **covered by the Free flat-rate plan once you attach it** (step 13).
   - **Don't enable DNSSEC.** The plan doc says DNSSEC has a separate AWS KMS cost.

### C. Certificate
4. Switch the console region to **us-east-1**. Go to **Certificate Manager (ACM) → Request → Request a public certificate.**
   - Fully qualified domain names: `erranddesk.com`, then **Add another name**: `www.erranddesk.com`.
   - Validation: **DNS validation**. Key algorithm: default (RSA 2048) → Request.
   - Open the certificate → **Create records in Route 53** → select both → Create records.
   - Wait for status **Issued** (usually minutes; can be longer right after registration).
   - Cost: $0 (public certificates for CloudFront are "No cost").
   - Note: the new CloudFront wizard may also offer **Create certificate**. Either path works, but don't create two.

### D. Storage
5. **S3 → Create bucket** (region **us-east-1**). Type: General purpose. Name: `erranddesk-com-site` (or any free name; write it down as BUCKET_NAME).
   - Object Ownership: **ACLs disabled**. **Block all public access: ON** (leave all 4 boxes checked).
   - Versioning off, default encryption SSE-S3 → Create bucket.
   - Do **not** enable "Static website hosting."
6. **Upload the site.** Open the bucket → **Upload** → drag the **contents** of `deploy/site/` (index.html, about/, guides/, assets/, sitemap.xml, robots.txt and the icon files), not the `site` folder itself → Upload.
   - Check that `index.html` sits at the bucket root.
   - Optional: use `upload-commands.sh` (AWS CLI) instead. It sets the cache headers (1 year for CSS and icons, 5 minutes for HTML).

### E. Edge function
7. **CloudFront → Functions → Create function.** Name: `erranddesk-viewer-request`. Runtime: **cloudfront-js-2.0** → Create.
   - In **Build**, replace the code with the full contents of `cloudfront-function-index-rewrite.js` → **Save changes**.
   - **Test** tab: Event type Viewer request; URL path `/guides/fax-prices/`, host header `erranddesk.com` → Test. The output URI should be `/guides/fax-prices/index.html`. A test with host `www.erranddesk.com` should return a 301 to `https://erranddesk.com/...`.
   - **Publish** tab → **Publish function**.
   - Don't reuse this function on any other distribution. Plan rules don't allow sharing it.

### F. CloudFront distribution
8. **CloudFront → Distributions → Create distribution.**
   - **Plan:** choose **Free ($0/month)**.
   - Distribution name: `erranddesk`. Type: **Single website or app**.
   - **Domain:** if offered, enter `erranddesk.com` → **Check domain**, then add the subdomain `www`.
   - Next.
9. **Origin:** Origin type **Amazon S3** → **Browse S3** → choose your bucket.
   - Settings: **Use recommended origin settings**. This sets up **Origin Access Control (OAC)**.
   - Next.
10. **Security:** keep the AWS WAF protections the wizard offers. A WAF web ACL is **required** for flat-rate plans and is included at no extra cost. Free plan: up to 5 rules.
    - Next.
11. **TLS certificate:** choose the **Issued** ACM certificate from step 4 (covers both names) → Next → review → **Create distribution**.
    - Write down the **Distribution ID** (E…) and **Distribution domain name** (d….cloudfront.net).
12. **Finish settings.** Open the distribution → **General → Settings → Edit**:
    - Alternate domain names: both `erranddesk.com` and `www.erranddesk.com` are listed (add any that are missing).
    - Custom SSL certificate: the step-4 certificate.
    - **Default root object:** `index.html`.
    - IPv6: **On**.
    - Save.
    - Then go to the **Behaviors** tab → select Default (*) → Edit:
      - Viewer protocol policy: **Redirect HTTP to HTTPS**.
      - Allowed methods: **GET, HEAD**.
      - Cache policy: **CachingOptimized** (keep what the wizard set).
      - **Function associations → Viewer request:** Function type **CloudFront Functions**, function `erranddesk-viewer-request`.
      - Save.
13. **Attach the hosted zone to the plan** (this is what makes the $0.50/month hosted-zone fee covered): distribution → **Manage plan** → attach Route 53 hosted zone `erranddesk.com`.
14. **Bucket policy.** CloudFront usually updates it for you when you use the recommended OAC settings. Check **S3 → bucket → Permissions → Bucket policy**:
    - If it's empty or different, paste `s3-bucket-policy.json` with `BUCKET_NAME`, `ACCOUNT_ID` (12 digits, top-right account menu) and `DISTRIBUTION_ID` filled in → Save.
    - Block Public Access stays **ON**.

### G. DNS
15. **Route 53 → Hosted zones → erranddesk.com → Create record** (or use **Route domains to CloudFront** on the distribution's General tab if shown). Create 4 alias records:
    - Name blank (apex), type **A**, **Alias ON** → Route traffic to **Alias to CloudFront distribution** → pick the distribution.
    - Name blank, type **AAAA**, Alias → same distribution.
    - Name `www`, type **A**, Alias → same distribution.
    - Name `www`, type **AAAA**, Alias → same distribution.
    - Alias queries to CloudFront are free.
16. Wait until the distribution's **Last modified** shows a date (not "Deploying").

### H. Test (in a private or incognito window)
17. Check each of these:
    - `https://erranddesk.com/` (home loads, padlock shown)
    - `https://erranddesk.com/guides/fax-prices/`
    - `https://erranddesk.com/guides/notary-options/`
    - `https://erranddesk.com/guides/passport-photo-prices/`
    - `https://erranddesk.com/about/`
    - `https://erranddesk.com/guides/fax-prices` (no trailing slash: should still load)
    - `https://erranddesk.com/sitemap.xml` and `https://erranddesk.com/robots.txt`
    - `https://erranddesk.com/favicon.ico` and `https://erranddesk.com/favicon.svg`
    - `http://erranddesk.com/` → redirects to https
    - `https://www.erranddesk.com/guides/notary-options/` → 301 to `https://erranddesk.com/guides/notary-options/`
    - `https://BUCKET_NAME.s3.amazonaws.com/index.html` → should be **Access Denied** (bucket is private)
18. **Billing → Bills** in a day or two: expect only the $16.00 domain charge (plus tax).

### I. Later (not now)
- Cloudflare Web Analytics: put the token in `site/site.config.json` (`cf_analytics_token`), rebuild, re-upload, invalidate.
- Search Console and Bing sitemap submission: after the live check, with approval.
- The Denver page: only after the national site is live and tested.

**Tell me when done, and share the CloudFront domain and distribution ID.**
