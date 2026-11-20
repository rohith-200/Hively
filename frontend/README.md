# Hivly frontend

**Brand:** hivly. · **Tagline:** Thoughtful finds. A space that’s yours.

Naman’s frontend follows the complete **Roomie — Tech Design & Team Plan** (Nov 20, 14 pages). Hivly is the frontend brand; the existing Roomie backend contract stays unchanged. All implementation is inside `frontend/`.

## Run

Requires Node.js 22.12+ (Node 24 recommended).

On Windows, double-click **Start-Hivly.cmd** in the project folder. It starts the local server in the background and opens Hivly. If Hivly is already running, it reuses the server.

From a terminal, `npm start` inside `frontend/` does the same background startup without opening a browser. The launcher checks both the page and API before reporting success. Startup logs are in `frontend/.hivly/`, which is excluded from Git.

```powershell
cd frontend
npm ci
npm run dev
```

`npm run dev` keeps the server attached to the terminal; closing that terminal stops it. Use the launcher or `npm start` when you want the server to keep running in the background.

Open **http://127.0.0.1:5173**. Choose **Try a sample**, select a living room, kitchen, or bedroom, and start the run. `npm run preview` serves the production build and mock API at http://127.0.0.1:4173. A bare static file server does not provide the mock API.

```powershell
npm test
npm run build
npm run preview
```

## What the product takes in and returns

| Input                               | Frontend behavior                                                                                                                                |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| One JPG/PNG room photo, up to 8 MiB | Upload, drag/drop, or phone camera; validates format, size, and whether the browser can decode it. Shows the original image throughout analysis. |
| Room budget                         | USD number and slider; item totals display separately from tax/shipping.                                                                         |
| Stores                              | Shopify, Amazon, Walmart toggles; sends the frozen comma-separated values.                                                                       |
| Optional note                       | Style, items to keep, must-haves, and things to avoid. Sent to the backend as `note`.                                                            |
| User ID                             | Configurable in the profile so Cognee can recall the team’s seeded user. Same ID is used for repeated rooms.                                     |

| Output                | How the UI presents it                                                                                                                                                        |
| --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Detected room profile | Backend room type, style, confidence, palette, evidence, materials. No hardcoded kitchen assumption.                                                                          |
| Agent decisions       | Reader, memory, Stylist, catalog search, Curator, Critic, guardrails, payment preparation. Received events complete stages; the next expected stage gets a working indicator. |
| Curated products      | Grouped by actual store, with item prices, reasons, optional fit score, and Critic notes.                                                                                     |
| Selected total        | Recomputed in integer cents; separates automatic-purchase items from cart/product-link items based on each item’s `execution_mode`.                                           |
| Approval result       | Per-store order/cart/product link, item count, amount, order ID, errors, and actual payment status/captured amount.                                                           |
| Audit                 | Backend-verified hash chain, readable results, optional full event JSON, fallback indicators.                                                                                 |

The app recommends a shopping collection; it **does not generate a renovated room image or a 3D room scene**. Decorative procedural 3D bees appear during onboarding and agent work, with lightweight animated bee illustrations used for loading states and as a WebGL fallback. The bee scene uses Three.js; built-in room samples remain flat illustrations converted to PNG uploads.

## Live integration and team ownership

Copy `.env.example` to `.env.local`, then restart Vite:

```dotenv
VITE_API_MODE=live
API_PROXY_TARGET=http://127.0.0.1:8000
VITE_API_BASE_URL=
```

| Owner   | Backend responsibility                                        | Frontend consumes                                                                                        |
| ------- | ------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| Jaideep | Claude vision + Arcee Stylist/Curator/Critic                  | `Run.room`, product reasons, Critic notes, `step` events and their data                                  |
| Suman   | SingleStore catalog/audit, Cognee memory, Amplitude mirror    | Products, memory events, `chain_valid`, service modes; frontend does not write directly to these systems |
| Rohit   | FastAPI, orchestration, guardrails, Stripe, merchant adapters | Frozen endpoints, run states, totals, payment info, and merchant results                                 |
| Naman   | Screens, API client, local mock API                           | Photo input → live steps → review → approval/rejection → results and audit                               |

The PDF’s initial real catalog covers **kitchens and living rooms**. The frontend accepts arbitrary indoor-room photos and displays any backend room type; actual matches for bedrooms, offices, or other spaces depend on vision support and catalog coverage. Empty results, skipped categories, failed input, partial execution, and unavailable store links have explicit UI states.

### Frozen API

| Operation                                                           | Endpoint                          |
| ------------------------------------------------------------------- | --------------------------------- |
| Service modes                                                       | `GET /api/health`                 |
| Multipart photo, `user_id`, `budget_usd`, `stores`, optional `note` | `POST /api/runs`                  |
| Current run                                                         | `GET /api/runs/{run_id}`          |
| `step`, `state`, `run`, `error` events                              | `GET /api/runs/{run_id}/events`   |
| Approve selected IDs                                                | `POST /api/runs/{run_id}/approve` |
| Reject with reason                                                  | `POST /api/runs/{run_id}/reject`  |
| Events + verification                                               | `GET /api/runs/{run_id}/audit`    |

SSE falls back to one-second status polling on disconnect. Audit failures or slow audit responses do not block run status. Events deduplicate by sequence number. During approval, the UI follows actual backend execution status; it does not simulate live purchases. Images under `/api` use the configured API base URL. For a separately hosted frontend, set backend CORS and `VITE_API_BASE_URL` accordingly.

Step data is intentionally extensible. A vision event can include `data.room_profile`, `data.profile`, or `data.room`; if it does not, the client refreshes the run after the vision step. Stylist queries, memory facts, and Critic changes are shown when those fields are present in the event. Unknown event data remains available in the audit details. Agent completion is never fabricated from an elapsed-time animation.

No secrets belong in `VITE_` variables: they are public browser configuration. No analytics calls are made directly from the frontend because the plan routes them through backend audit events.

## Mock behavior

- The local mock API lives in `mocks/server.ts`, not in the team’s backend folder. Its eight preparation steps replay every **600 ms**.
- Exact built-in sample identifiers choose kitchen/living-room/bedroom/office fixtures. **Arbitrary filenames and uploads are not classified locally.** They produce an explicitly unclassified demo profile and example recommendations. Photo-specific recommendations need Jaideep’s live vision and the real catalog.
- Built-in sample room illustrations are flat SVG assets converted to valid PNG uploads. Product images are local illustrations of fictional demo products.
- Mock selections obey the chosen stores and budget. Approvals create local cart-preview dialogs and simulated payment amounts; they do not place real orders, charge money, or create real Amazon/Walmart carts.
- Approved/removal choices are remembered in the local mock process and recalled for a second run with the same user ID. This exercises the memory UI but is not Cognee integration.
- The mock audit hash chain is genuinely SHA-256 computed and verified. The live UI trusts the backend’s `chain_valid` result and does not reimplement its canonicalization.
- Demo runs, uploads, and demo taste memory disappear when Vite stops. Only profile fields and the motion preference persist in browser local storage.

## UX and validation

Photo-first upload, detailed agent progress, store-grouped review, sticky desktop summary, mobile approval bar, smooth page transitions, spring dialogs, Escape to close, visible focus, dialog focus trapping, a skip link, original-photo enlargement, and system/in-app reduced motion. Store checkout behavior follows **each item’s execution mode**, including Shopify cart fallbacks. Temporary holds and final selected automatic-purchase amounts are shown separately.

Tests exercise HTTP multipart/SSE, distinct room scenarios, unknown uploads, budget/store filtering, empty results, edited approval amounts, duplicate approvals, rejection/hold release, repeated-user demo memory, hash tampering, event-driven stages, SSE fallback, stalled audit requests, and subscription cleanup. Live end-to-end validation still requires the team’s backend and fixtures.

## Files

| Path                                  | Purpose                                                    |
| ------------------------------------- | ---------------------------------------------------------- |
| `src/App.tsx`                         | Workflow coordination, profile, sample picker, and dialogs |
| `src/components/RoomStage.tsx`        | Original-photo upload, preview, and enlargement            |
| `src/components/BeeScene.tsx`        | Decorative 3D bee scene and lightweight loading bee       |
| `src/components/UploadPanel.tsx`      | Budget, stores, note, submission                           |
| `src/components/AgentWorkspace.tsx`   | Event-driven agent progress                                |
| `src/components/ReviewCollection.tsx` | Store groups, selectable products, totals and approval     |
| `src/components/RunResults.tsx`       | Merchant results and payment outcomes                      |
| `src/components/AuditTrail.tsx`       | Verification, readable outputs and event data              |
| `src/lib/api.ts`                      | HTTP, SSE, independent polling, asset URLs                 |
| `src/lib/workflow.ts`                 | Agent mapping and presentation helpers                     |
| `mocks/`                              | Frontend-only fixtures and local API                       |

Regenerate flat sample images with `node scripts/create-samples.mjs` and product illustrations with `node scripts/create-assets.mjs`.
