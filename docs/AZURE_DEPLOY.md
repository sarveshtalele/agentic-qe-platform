# Deploy Agentic QE Platform to Azure

This guide puts Agentic QE Platform on Azure App Service with the Azure portal and two ZIP files. You do not need GitHub or anything installed on your machine except Python and Git, which you already use to run Agentic QE Platform.

**Not yet deployed for real on Azure.** **Tested so far:** the ZIPs were unpacked and their startup scripts run locally on macOS, including the environment build, the second start that skips it, the UI proxy to the API, and the SQLite setting. **Not tested:** a real Azure deployment, which needs your subscription. Steps marked *check on first use* could not be confirmed from Microsoft's documentation.

> This guide deploys the app as it runs today: one process with SQLite and local files, suited to one person or a small trusted team. For several users, read `docs/AZURE_SYSTEM_DESIGN.md`, which covers PostgreSQL, Blob Storage, and isolated sandboxes.

## What it costs

Prices come from the [Azure Retail Prices API](https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices) with `currencyCode=INR`, fetched on 1 November 2026. Monthly figures use 730 hours and exclude taxes.

| Plan | Region | ₹ per hour | ₹ per month |
|---|---|---|---|
| **Basic B1 Linux (recommended)** | **East US 2** | **1.6189** | **1,181.80** |
| Basic B1 Linux | East US | 1.6189 | 1,181.80 |
| Basic B1 Linux | Central India | 1.7141 | 1,251.29 |
| Basic B1 Linux | Southeast Asia | 1.7141 | 1,251.29 |
| Basic B1 Linux | South India, West India | 1.8093 | 1,320.79 |
| Basic B2 Linux | East US | 3.2378 | 2,363.59 |
| Basic B1 Windows | East US | 7.1422 | 5,213.81 |
| Free F1 Linux | Any | 0 | 0 |

| Total for Agentic QE Platform | ₹ per month |
|---|---|
| One B1 Linux plan in East US 2, holding both apps | 1,181.80 |
| Storage, 10 GB included with Basic | 0 |
| Outbound data, first 100 GB | 0 (then ₹10.48 per GB, Central India rate) |
| **Total** | **about ₹1,182** |

Your model provider bills separately and is not included.

**Why B1 in East US 2.** It is the cheapest plan that can run Agentic QE Platform, and one plan holds both apps. East US 2 is also where your model endpoint runs, so agent calls stay short. Choose Central India instead if your data must stay in India: it costs ₹69.49 more a month and pages load faster from India.

**Why not Free F1.** Microsoft limits it to 60 CPU minutes a day and 1 GB of storage, with no Always On. Agent workflows run in the background, so they would stop when the app goes idle.

**A plan bills while it exists, even with the apps stopped.** To stop paying, delete the resource group.

## 1. Make the ZIP files

From the project folder:

```bash
python scripts/package_azure.py
```

This creates `dist/agentic-qe-backend.zip` and `dist/agentic-qe-frontend.zip`. They exclude tests, `.env`, runtime data, and `node_modules`.

## 2. Create the backend app

1. In the [Azure portal](https://portal.azure.com), choose **Create a resource**, then **Web App**.
2. On **Basics**, set:
   - **Resource group:** create `agentic-qe-rg`
   - **Name:** for example `agentic-qe-api-yourname`
   - **Publish:** Code
   - **Runtime stack:** Python 3.12
   - **Operating System:** Linux
   - **Region:** East US 2
   - **Linux Plan:** create `agentic-qe-plan`
   - **Pricing plan:** Basic B1. It may be under **Explore pricing plans**.
3. On **Monitoring**, turn **Application Insights** off, because it can add cost.
4. Choose **Review + create**, then **Create**.
5. Open the app and copy **Default domain** from **Overview**. Azure may add random characters to it, so always copy it rather than typing it.

## 3. Create the frontend app

Repeat step 2 with these changes:

- **Name:** for example `agentic-qe-ui-yourname`
- **Runtime stack:** Node 22 LTS
- **Linux Plan:** the existing `agentic-qe-plan`, which adds no cost

Copy this app's **Default domain** too.

## 4. Add settings to both apps

Open each app, then **Settings > Environment variables**. Add these, choose **Apply**, and confirm.

**Backend**

| Name | Value |
|---|---|
| `ATLAS_ALLOWED_HOSTS` | Backend default domain |
| `ATLAS_ALLOWED_ORIGINS` | `https://` + frontend default domain |
| `ATLAS_ADMIN_USERNAME` | The admin's username. Required for anyone to sign in |
| `ATLAS_ADMIN_PASSWORD` | A long, unique password. Azure encrypts this setting at rest |
| `WEBSITES_CONTAINER_START_TIME_LIMIT` | `1800` |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | `false` |
| `ATLAS_SESSION_IDLE_MINUTES` | Optional. Minutes without activity before a session ends. Default 480 |
| `ATLAS_LOG_RETENTION_DAYS` | Optional. Days of daily log files to keep. Default 30 |

**Frontend**

| Name | Value |
|---|---|
| `ATLAS_BACKEND_URL` | `https://` + backend default domain |
| `WEBSITES_CONTAINER_START_TIME_LIMIT` | `1800` |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | `false` |

Enter the model URL, model name, and API key later on the Agentic QE Platform **Settings** page. Agentic QE Platform encrypts them at rest.

## 5. Set startup commands

Open each app, then **Settings > Configuration > General settings**. On newer portals this may be **Stack settings**.

| Setting | Backend | Frontend |
|---|---|---|
| Startup Command | `python /home/site/wwwroot/startup.py` | `node /home/site/wwwroot/startup.js` |
| Always On | On | On |
| HTTPS Only | On | On |
| Health check path, under **Monitoring > Health check** | `/api/health` | `/` |

## 6. Upload the ZIP files

Microsoft states that the Kudu ZIP drag-and-drop page **does not work on Linux** App Service, so use one of these routes.

### Route A: Cloud Shell (recommended)

This runs in your browser and is Microsoft's documented method.

1. Select the **Cloud Shell** icon at the top of the portal and choose **Bash**. If asked about storage, choose **No storage account required**.
2. Choose **Manage files > Upload** and upload `agentic-qe-backend.zip`, then `agentic-qe-frontend.zip`.
3. Run these, with your app names:

```bash
az webapp deploy --resource-group agentic-qe-rg --name agentic-qe-api-yourname --src-path agentic-qe-backend.zip --type zip --async true
```

```bash
az webapp deploy --resource-group agentic-qe-rg --name agentic-qe-ui-yourname --src-path agentic-qe-frontend.zip --type zip --async true
```

### Route B: Kudu files and SSH (*check on first use*)

1. Open the app, then **Development Tools > Advanced Tools > Go**. Kudu opens in a new tab.
2. Open the Kudu **File Manager**, go to `/home`, and upload the ZIP there.
3. Open **SSH** from Kudu, or from **Development Tools > SSH** in the portal, and unpack it.

Backend:

```bash
python -m zipfile -e /home/agentic-qe-backend.zip /home/site/wwwroot
```

Frontend:

```bash
unzip -o /home/agentic-qe-frontend.zip -d /home/site/wwwroot
```

4. In the portal, choose **Restart** on **Overview**.

## 7. Watch the build

Open **Monitoring > Log stream** on each app. Lines from Agentic QE Platform start with `[agentic-qe]`.

| Log line | Meaning |
|---|---|
| `Building environment in /home/atlas/venv` | First backend start. Several minutes |
| `Building in /tmp/atlas-build-…` | First frontend start. Often the slowest step on B1 |
| `Environment is current; skipping install` | Normal restart |
| `Starting API on port …`, `Starting UI on port …` | Ready |

Start the backend first and wait for it to finish, because both apps share 1.75 GB of memory on B1. If the frontend build runs out of memory, scale the plan to B2 for the first build, then scale back. Billing is per hour.

## 8. Protect it before anyone uses it

The app now has its own sign-in, but it can run repository code, so also keep the backend private.

**Allow only the frontend to reach the backend**

1. Open the frontend app, then **Settings > Properties**, and copy **Outbound IP addresses**.
2. Open the backend app, then **Settings > Networking > Access restriction**.
3. Set unmatched public traffic to **Deny**, and add an **Allow** rule for each address, written as `address/32`.
4. Keep the **Advanced tool site** (Kudu) rules at their defaults, so you can still upload.

Check that the backend's address now refuses your browser and that the frontend shows the sign-in page.

**Optional second layer.** To limit who can even reach the sign-in page, turn on **Settings > Authentication** with Microsoft as the provider on the frontend.

## 9. First run checks

1. Open the frontend address and sign in as the admin.
2. Open **Settings**, enter the model details, and choose **Test connection**. Under **Models**, choose **Load from proxy**, and test each model before you switch it on.
3. Open **Users**, create the first user, and tick the models that user may use.
4. Check that **System health** shows Git and Ruff as ready. *Check on first use: Git and Node.js come from Azure's Python image.*
5. Create a project from a small public repository and run a bug scan.

## Updating

1. Run `python scripts/package_azure.py` again.
2. Upload as in step 6.
3. Watch the log stream. The startup scripts rebuild only what changed, and your data stays in `/home/atlas/data`.

To roll back, upload your previous ZIP files, so keep them.

## Backup

All state is in `/home/atlas/data`, including `.secret.key`, which decrypts stored keys, and the daily logs in `/home/atlas/data/logs`. Download it from Kudu's File Manager, or use **Settings > Backups** on higher tiers. Basic has no automated backup. Keep the backup private.

## Known limits

| Limit | Effect | Fix when it matters |
|---|---|---|
| One instance, one worker | Workflows run inside the API process, and a restart marks running ones as interrupted. Choose Retry failed stage on each one | Move runs to a queue before scaling out |
| SQLite on the `/home` network share | Works for one user. It is slower than a local disk | Move to Azure SQL or PostgreSQL for several users |
| Azure closes requests after about 230 seconds with no response | A very long clone or chat reply can fail. Run progress uses a stream with keep-alives | Use smaller repositories. A higher tier does not change this limit |
| Repository install scripts run on this server | A hostile repository could reach your data | Tick install dependencies only for repositories you trust |
| 10 GB of storage on Basic | Large repositories and worktrees use it up | Delete old projects, or scale up |
