# Xortify product and revenue roadmap

## Product position

Xortify is a Windows desktop product that organizes files on the customer's computer. It is not SaaS today: there is no hosted account, cloud inference, sync service, or ongoing server cost. That is a useful selling point for people who do not want private files uploaded.

Suggested one-line pitch:

> Sort loose files and photos locally, while keeping every recognized project folder intact.

Start with one paying audience instead of “everyone”: photographers and hobbyists with scattered photo collections, or students/creators with messy Downloads folders. Ask which group has the strongest repeated pain before building more.

## Roadmap

| Stage | Product work | Business work | Exit signal |
| --- | --- | --- | --- |
| 0. Validate | Use disposable folders to test category quality, project detection, collisions, undo, and offline AI. | Interview 15–20 people from two likely audiences. Show the review screen. Ask about their current cleanup habits and whether they would pay. | One audience repeatedly describes the same problem and a few people agree to try an early build. |
| 1. Private beta | Improve false-positive handling, preview clarity, Windows installer, backup/restore guidance, and crash reporting that never collects file data by default. Add a “why this suggestion?” explanation and easy corrections. | Recruit 20–30 testers from the chosen audience. Ask for permission before any diagnostic file is shared. | Most testers finish a first scan, understand the plan, and can undo a test move without help. |
| 2. Commercial readiness | Clear model/data/dependency licenses; replace the current ImageNet prototype if commercial rights are not confirmed. Test Windows 10/11 installs, upgrades, uninstall, interrupted moves, and larger folders. Sign release builds. | Set up a publisher identity, support email, privacy page, refund terms, and payment/tax handling for the seller's country. | No unresolved release-blocking data/license issue; support and payment flows are ready. |
| 3. First paid release | Keep safe scan/preview and basic organization available free. Offer a Pro edition with larger/batch plans, saved organization profiles, richer rules, configurable collections, and extended journal history. Keep all base sorting offline. | Start with a one-time Pro purchase or paid major-version upgrades. Test the price with real users. Avoid a subscription until there is a recurring service customers actually receive. | People outside the tester group buy it, finish onboarding, and return to use it again. |
| 4. Grow carefully | Improve photo grouping based on corrections. Add a second model only when it solves a measured problem. Consider video key-frame grouping after performance and licensing are clear. | Publish short demos and practical cleanup guides. Ask photographers, student groups, and Windows creator communities for feedback. Add small-business/team licenses if teams request shared rules. | Organic referrals and repeat use grow without support costs exceeding revenue. |
| 5. Optional services | Only if customers request them, consider encrypted backup/sync, team profiles, or managed deployments as a separate opt-in product. | A paid cloud tier can create recurring revenue, but introduces hosting, security, support, and privacy obligations. Keep local sorting usable without it. | Customers explicitly value the service enough to cover its ongoing operating and support cost. |

## How to earn from it

### 1. Sell a desktop license first

The product's current value is local organization software. A simple model is:

- Free: scan, preview, basic categories, and a small number of approved moves or saved profiles.
- Pro: larger/batch plans, custom rules and collections, more saved profiles, advanced review tools, and longer local history.
- Future team plan: shared organization profiles and managed deployment for small businesses.

Price after interviews and beta use. Track gross sales, refunds, payment/platform fees, taxes, support time, and upgrade purchases; downloads alone are not proof of a business.

### 2. Sell where Windows users can find it

Use a product website for clear demos, privacy details, download instructions, and help. Consider the Microsoft Store for discovery and simpler updates. Microsoft's current publishing guide says the new individual developer onboarding flow has no registration fee. It also describes a choice between using the developer's own commerce system for non-gaming apps or Microsoft's commerce platform, which currently charges a 15% app fee. The actual checkout choice and taxes depend on the seller's country and setup. See [Microsoft Store publishing](https://learn.microsoft.com/en-us/windows/apps/publish/get-started) and [developer account setup](https://learn.microsoft.com/en-us/windows/apps/publish/partner-center/open-a-developer-account).

### 3. Do not force a SaaS subscription

The local model does not create a monthly cloud bill. A one-time license can fit better than a subscription. Add recurring billing only for a clear ongoing benefit such as optional backup/sync, team administration, or continuing major updates. Never make customers pay monthly just to keep using files already stored on their PC.

## What must be true before taking money

1. **Clear the current model or replace it.** The model artifact says Apache 2.0, while ImageNet's access agreement states non-commercial research/education terms. Get qualified advice on the checkpoint's commercial status or switch to a commercially cleared model and dataset. Do not distribute the current checkpoint in a paid installer until this is resolved.
2. **Show honest AI limits.** The current model predicts from a fixed 1,000-class list. It can group common cat classes under Cats; it cannot understand custom descriptions, family relationships, video scenes, or document contents.
3. **Prove the safe move path.** Test project-folder moves on disposable repos, include Git metadata, preserve internal paths, and verify undo after a collision.
4. **Ship a trustworthy installer.** The project is Python/PySide6. The optional model file is only about 4.91 MiB, but Python, Qt, NumPy, ONNX Runtime, and Pillow add more installed size. Measure the built installer rather than quoting the model weight size as the full app size.
5. **Keep private data private.** No content telemetry by default. If crash diagnostics are added, ask separately and strip local paths and filenames.

## Measure product-market fit

Instrument only non-content product events if users opt in; otherwise collect feedback directly:

- percentage of users who complete their first scan;
- percentage who accept at least one suggestion;
- how often users edit or reject an AI placement;
- undo rate and failed-move rate;
- repeat use after one week and one month;
- paid conversion, refunds, and support minutes per buyer.

The feedback that matters most is where the model is wrong and whether a corrected placement saves time next time. Store corrections locally by default and make any export/import user-controlled.

## Revenue math

Use:

~~~text
net revenue = paid customers × price
              − storefront/payment fees
              − taxes, refunds, and chargebacks
              − support and operating costs
~~~

Do not build cloud infrastructure, subscriptions, or a large marketing budget before a beta group uses the software repeatedly and pays for the desktop features.
