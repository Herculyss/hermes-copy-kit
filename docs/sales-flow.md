# CopySnap go-live checklist

Public URLs
- Gumroad product: https://fuioherm.gumroad.com/l/copysnap
- App: https://benevolent-mermaid-18d8b0.netlify.app/
- API: https://web-production-b07a1.up.railway.app

Customer journey
1. Customer buys on Gumroad.
2. Gumroad sends a POST to https://web-production-b07a1.up.railway.app/gumroad/webhook
3. CopySnap generates and stores the license key.
4. Customer opens the app.
5. Customer either pastes the license key or clicks "Retrieve my license key" and enters the same purchase email.
6. Unlimited access unlocks.

Endpoints
- POST /generate-license
- POST /verify-license
- POST /retrieve-license
- POST /gumroad/webhook

What to configure in Gumroad
- Ping / webhook URL: https://web-production-b07a1.up.railway.app/gumroad/webhook
- Product URL stays: https://fuioherm.gumroad.com/l/copysnap
- App URL for customers: https://benevolent-mermaid-18d8b0.netlify.app/

Recommended receipt copy
Thanks for purchasing CopySnap.
Open https://benevolent-mermaid-18d8b0.netlify.app/
If your key is not shown automatically, click "Retrieve my license key" and use the same email you used on Gumroad.
