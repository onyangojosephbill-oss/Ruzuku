# Ruzuku

A directory of research grants and fellowships for scholars in Kenya and across Africa, grouped by field and labelled Kenya or International. A scheduled job on GitHub reads funder feeds every day, adds new calls to `data/grants.json`, and republishes the site.

## What is in this folder

| File | What it does |
| --- | --- |
| `index.html` | The website. It loads `data/grants.json` when someone opens it. |
| `data/grants.json` | The list of grants. Hand-checked entries have `"auto": false`. Entries found by the daily job have `"auto": true`. |
| `data/sources.json` | The feeds the daily job reads. You can add and remove sources. |
| `scripts/update_grants.py` | The job that reads the feeds and updates `grants.json`. |
| `scripts/page.js` | A readable copy of the site's script, for reference. The site itself does not need it. |
| `.github/workflows/update.yml` | Tells GitHub to run the job every day and publish the site. |

## Put it online (about 15 minutes)

You need a free GitHub account. Go to github.com and choose Sign up if you do not have one.

### 1. Create the repository

1. Sign in to GitHub. Select the **+** at the top right, then **New repository**.
2. Name it `ruzuku`. Choose **Public**. Free GitHub Pages sites need a public repository.
3. Leave "Add a README" unticked. Select **Create repository**.

### 2. Upload the files

1. On the new empty repository page, select **uploading an existing file**.
2. Unzip `ruzuku-site.zip` on your computer. Open the folder and drag these into the browser window: `index.html`, the `data` folder, the `scripts` folder and `README.md`.
3. Scroll down and select **Commit changes**.

### 3. Add the workflow file

Folders that start with a dot are often skipped when you drag and drop, so create this file in the browser instead.

1. In the repository, select **Add file**, then **Create new file**.
2. In the name box, type exactly: `.github/workflows/update.yml`. When you type each `/`, GitHub turns the text before it into a folder.
3. Open `update.yml` from the unzipped folder in any text editor (Notepad works). Copy everything and paste it into the large box on GitHub.
4. Select **Commit changes**, then **Commit changes** again in the pop-up.

### 4. Turn on GitHub Pages

1. Open the repository's **Settings** tab.
2. In the left menu, select **Pages**.
3. Under **Build and deployment**, set **Source** to **GitHub Actions**.

### 5. Run it once

1. Open the **Actions** tab. If GitHub asks you to enable workflows, select the green button.
2. Select **Update grants and deploy** in the left list, then **Run workflow**, then the green **Run workflow** button.
3. Wait two to three minutes until the run shows a green tick. Select the run, then the `update-and-deploy` job, to see the address of the live site.
4. Your site is at `https://YOUR-USERNAME.github.io/ruzuku/`.

If the run fails with a permissions error, open **Settings**, then **Actions**, then **General**. Under **Workflow permissions**, choose **Read and write permissions**, select **Save**, and run the workflow again.

### 6. Link it from anywhere

Share the address from step 5. To link it from your profile, select the gear icon next to **About** on the repository's front page and tick **Use your GitHub Pages website**.

If you own a domain name, go to **Settings**, then **Pages**, and enter it under **Custom domain**. GitHub shows the DNS records to add at your domain registrar.

## How the automatic updates work

Every day at 07:00 Nairobi time, GitHub runs `scripts/update_grants.py`. The script:

1. Reads each feed listed in `data/sources.json`.
2. Keeps items that look like grants or fellowships, and drops jobs, tenders and webinars.
3. Guesses the field, the deadline, the amount and whether it is Kenyan or international from the announcement text.
4. Adds items that are new and not yet closed, labelled **Auto-found, unchecked**.
5. Removes auto-found entries about three months after their deadline passes.
6. Saves `data/grants.json` and republishes the site.

Entries you wrote or checked by hand are never changed or removed by the script.

### What it cannot do

- It cannot read websites that have no feed. Only feeds listed in `data/sources.json` are checked.
- The field, deadline and amount of auto-found entries are guesses. Check the funder page before you apply.
- The feed addresses in `sources.json` follow the usual pattern for WordPress sites and have not been tested from the live internet. After the first run, open the run's log under **Actions**. Each source shows either `[ok]` with the number of items read, or `[skip]` with the reason. Remove or replace any source marked `[skip]`.

## Everyday jobs

**Add a source.** Open `data/sources.json` on GitHub, select the pencil icon, and copy one of the existing blocks. Set `scope` to `kenya` or `international`. Set `require_region` to `true` for general feeds, so only items that mention Africa, Kenya or developing countries are kept.

**Fix or confirm an auto-found entry.** Open `data/grants.json`, find the entry, correct it, and change `"auto": true` to `"auto": false`. The script will leave it alone from then on.

**Remove an entry for good.** Delete it from `grants.json` and add its web address to `ignore_urls` in `sources.json`, or the job will find it again.

**Add a grant by hand.** Copy an existing entry in `grants.json`. Keep `scope` as `kenya` or `international`, and `cats` as any of `humanities`, `health`, `physical`, `environment`, `any`. Use `null` for `deadline` when there is none. Dates use the form `2026-11-30`.

**Run the update at any time.** Open **Actions**, select **Update grants and deploy**, then **Run workflow**.

**Try it on your own computer.** Run `python3 -m http.server` in this folder and open `http://localhost:8000`. Opening `index.html` by double-click will not work, because browsers block the file from loading `data/grants.json`.
