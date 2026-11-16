# Xortify product and revenue roadmap

## Product position

Xortify is a Windows desktop product that organizes files on the customer's computer. It is not SaaS today: there is no hosted account, cloud service, or sync service.

Suggested one-line pitch:

> Sort files into folders and review each move before it happens.

Start with one paying audience instead of “everyone”: photographers and hobbyists with scattered photo collections, or students/creators with messy Downloads folders. Ask which group has the strongest repeated pain before building more.

## Roadmap

| Stage | Product work | Business work | Exit signal |
| --- | --- | --- | --- |
| 0. Validate | Use disposable folders to test sorting suggestions, project detection, collisions, and undo. | Interview people from two likely audiences. Show the review screen. Ask about their current cleanup habits and whether they would pay. | One audience repeatedly describes the same problem and a few people agree to try an early build. |
| 1. Private beta | Improve false-positive handling, preview clarity, Windows installer, backup/restore guidance, and crash reporting that never collects file data by default. Add a “why this suggestion?” explanation and easy corrections. | Recruit 20–30 testers from the chosen audience. Ask for permission before any diagnostic file is shared. | Most testers finish a first scan, understand the plan, and can undo a test move without help. |
| 2. Commercial readiness | Review third-party component terms; replace the optional photo-grouping component if commercial rights are not confirmed. Test Windows 10/11 installs, upgrades, uninstall, interrupted moves, and larger folders. Sign release builds. | Set up a publisher identity, support email, privacy page, refund terms, and payment/tax handling for the seller's country. | No unresolved release-blocking license issue; support and payment flows are ready. |
| 3. First paid release | Keep safe scan/preview and basic organization available free. Offer a Pro edition with larger/batch plans, saved organization profiles, richer rules, configurable collections, and extended journal history. Keep all base sorting offline. | Start with a one-time Pro purchase or paid major-version upgrades. Test the price with real users. Avoid a subscription until there is a recurring service customers actually receive. | People outside the tester group buy it, finish onboarding, and return to use it again. |
| 4. Grow carefully | Improve sorting suggestions based on user feedback. Add new features when they address a measured problem. | Publish short demos and practical cleanup guides. Ask photographers, student groups, and Windows creator communities for feedback. Add small-business/team licenses if teams request shared rules. | Organic referrals and repeat use grow without support costs exceeding revenue. |
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

Local sorting does not create a monthly cloud bill. A one-time license can fit better than a subscription. Add recurring billing only for a clear ongoing benefit such as optional backup/sync, team administration, or continuing major updates. Never make customers pay monthly just to keep using files already stored on their PC.

## What must be true before taking money

1. **Review third-party terms.** The optional photo-grouping component has a commercial-use question recorded in [third-party notices](THIRD_PARTY_NOTICES.md). Resolve it or replace that component before including it in a paid release.
2. **Describe features plainly.** Photo grouping covers some familiar subjects. Keep it optional and let users review suggestions before moving files.
3. **Prove the safe move path.** Test project-folder moves on disposable repos, include Git metadata, preserve internal paths, and verify undo after a collision.
4. **Ship a trustworthy installer.** Measure the full installer, including its dependencies, instead of estimating the app size from individual components.
5. **Keep private data private.** No content telemetry by default. If crash diagnostics are added, ask separately and strip local paths and filenames.

## Measure product-market fit

Instrument only non-content product events if users opt in; otherwise collect feedback directly:

- percentage of users who complete their first scan;
- percentage who accept at least one suggestion;
- how often users edit or reject a sorting suggestion;
- undo rate and failed-move rate;
- repeat use after one week and one month;
- paid conversion, refunds, and support minutes per buyer.

The feedback that matters most is where a suggestion is wrong and whether a correction saves time later. Store corrections locally by default and make any export/import user-controlled.

## Revenue math

Use:

~~~text
net revenue = paid customers × price
              − storefront/payment fees
              − taxes, refunds, and chargebacks
              − support and operating costs
~~~

Do not build cloud infrastructure, subscriptions, or a large marketing budget before a beta group uses the software repeatedly and pays for the desktop features.
