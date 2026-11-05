# Deploying the Protein Function Predictor (free, Oracle Cloud)

The whole app (website, API and all four structural levels) runs as one Docker
container on a free Oracle Cloud virtual machine, behind Caddy, which provides
HTTPS automatically. Total cost: nothing.

| What | Why it fits |
| --- | --- |
| Oracle Cloud **Always Free** VM: 2 Arm CPUs, 12 GB memory, up to 200 GB disk | The app needs about 4 GB of memory (ProtBert, ESM-2, DIAMOND) and about 10 GB of disk (Swiss-Prot and Pfam databases, models) and must stay on while an analysis runs (15–30 minutes for a new sequence). Free "platform" hosts offer 512 MB. |
| **DuckDNS** subdomain, e.g. `protfunc.duckdns.org` | A free web address; Caddy gets a free HTTPS certificate for it. |
| `deploy/` folder | `Dockerfile` (builds everything), `docker-compose.yml` + `Caddyfile` (app + HTTPS), `setup_server.sh` (one-time server setup). |

Time needed: about 1 hour, most of it waiting for the first build.

---

## Part A. Prepare the repository (on your Mac)

1. **Optional, recommended:** analyse every example protein once in your local
   app, so they open instantly on the website. Then copy the saved results:

   ```bash
   cd ~/Projects/Bioinformatics_server/UI/backend
   bash scripts/update_seed_cache.sh
   ```

2. **Commit and push** (from the repository root):

   ```bash
   cd ~/Projects/Bioinformatics_server
   git add UI
   git status            # UI/backend/.env must NOT be listed
   git commit -m "Add deployment files"
   git push origin main
   ```

3. **Only if the GitHub repository is private:** create a token the server can
   use to download it. GitHub → your picture → **Settings** → **Developer settings**
   → **Personal access tokens** → **Fine-grained tokens** → **Generate new token**:
   repository access *Only select repositories* → this repository; permissions
   *Contents: Read-only*. Copy the token (it is shown once).

## Part B. Create the Oracle Cloud account

1. Go to <https://www.oracle.com/cloud/free/> → **Start for free**.
2. **Home region:** choose one close to you (e.g. *India South (Hyderabad)* or
   *India West (Mumbai)*). It cannot be changed later, and free machines can only
   be created there.
3. Verify with a credit or debit card (a small temporary charge is reversed; Indian
   cards need international/online transactions enabled). You stay on the free
   plan; nothing is charged as long as you only use "Always Free" resources.
4. Wait for the e-mail saying the account is ready, then sign in to the console.

## Part C. Create the server

Console → menu **☰** → **Compute** → **Instances** → **Create instance**.

1. **Name:** `protfunc`.
2. **Image and shape** → **Edit**:
   * **Change image** → **Canonical Ubuntu** → version **24.04** → **Select image**.
   * **Change shape** → **Ampere** → **VM.Standard.A1.Flex** → **OCPUs: 2**,
     **Memory: 12 GB** → **Select shape**. It should be marked *Always Free-eligible*.
3. **Networking:** keep *Create new virtual cloud network* and *Create new public
   subnet*; make sure **Assign a public IPv4 address** is on.
4. **Add SSH keys:** **Generate a key pair for me** → **Save private key**
   (a file like `ssh-key-2026-11-05.key`).
5. **Boot volume:** tick **Specify a custom boot volume size** → **100 GB**
   (free up to 200 GB in total).
6. **Create.** When the state is **Running**, copy the **Public IP address**.

> **"Out of capacity for shape VM.Standard.A1.Flex"** is common: try another
> *Availability domain* in step 2 (if your region has several), try again a few
> hours later, or use 1 OCPU / 6 GB (the app still works, more slowly).

## Part D. Open the web ports in Oracle's firewall

Instance page → **Primary VNIC** → click the **Subnet** name → **Security**
(or **Security Lists**) → **Default Security List** → **Add Ingress Rules**:

| Source CIDR | IP protocol | Destination port range |
| --- | --- | --- |
| `0.0.0.0/0` | TCP | `80` |
| `0.0.0.0/0` | TCP | `443` |

(Add them as two rules.) The server's own firewall is opened by `setup_server.sh`.

## Part E. Get the web address (DuckDNS)

1. <https://www.duckdns.org> → sign in (e.g. with GitHub).
2. Type a subdomain, e.g. `protfunc` → **add domain**.
3. In the **current ip** box, enter the server's public IP → **update ip**.

Your address is now `protfunc.duckdns.org`. (With your own domain instead, add an
**A record** pointing to the server's IP at your domain provider.)

## Part F. Install and start the app (on the server)

1. **Connect** from your Mac's Terminal (use your key file's real name):

   ```bash
   mv ~/Downloads/ssh-key-2026-11-05.key ~/.ssh/protfunc.key
   chmod 600 ~/.ssh/protfunc.key
   ssh -i ~/.ssh/protfunc.key ubuntu@YOUR_SERVER_IP
   ```

   Type `yes` when asked about the fingerprint. The prompt changes to `ubuntu@protfunc`.

2. **Start a tmux session**, so the build keeps running if the connection drops
   (reconnect later with `tmux attach -t deploy`):

   ```bash
   tmux new -s deploy
   ```

3. **Download the repository** (replace OWNER/REPO with yours; for a private
   repository, enter your GitHub username and paste the token from Part A as the
   password):

   ```bash
   sudo apt-get update && sudo apt-get install -y git
   git clone https://github.com/OWNER/REPO.git
   cd REPO/UI/deploy
   ```

4. **Run the setup script:**

   ```bash
   bash setup_server.sh
   ```

   It asks for the web address (`protfunc.duckdns.org`) and your Swiss-Model token
   (hidden while typing), then builds and starts everything. The first build takes
   about 30–40 minutes: it downloads Swiss-Prot and Pfam, builds the DIAMOND and
   HMMER databases and downloads the ESM-2 and ProtBert models.

5. When it prints **Done**, open `https://protfunc.duckdns.org`.

## Part G. Check it

* The header shows **Server online**.
* Run **Hemoglobin α**: with the saved results it finishes within seconds and
  shows *Hemoglobin subunit alpha*, confidence *High*.
* Paste a new sequence to test the live run (15–30 minutes).

Useful commands (on the server, in `REPO/UI/deploy`):

| Task | Command |
| --- | --- |
| Status | `sudo docker compose ps` |
| App log (Ctrl+C stops following) | `sudo docker compose logs -f app` |
| Restart the app | `sudo docker compose restart app` |
| Stop / start everything | `sudo docker compose down` / `sudo docker compose up -d` |

## Part H. Updating the website after a change

On your Mac: commit and push. Then on the server:

```bash
cd ~/REPO && git pull
cd UI/deploy && sudo docker compose up -d --build
sudo docker image prune -f        # removes the old image to free disk space
```

Code-only changes rebuild in a few minutes; the databases and models are reused.

## Part I. Demo day and good to know

* **A web service is down** (Swiss-Model, JPred, …): add
  `PFP_PLACEHOLDER_LEVELS=tertiary` (or the affected level) to `deploy/.env`, then
  `sudo docker compose up -d`. The final prediction uses the remaining levels.
* **Analyses run one at a time;** others wait in a queue. Results are kept until the
  app restarts; saved results of finished levels survive restarts.
* **Oracle reclaims idle free machines** (CPU, network and memory all below 20% for
  7 days). Loading the models at start-up (`PFP_PRELOAD_MODELS=on`) keeps memory use
  above that.
* **The Swiss-Model token** is stored only in `deploy/.env` on the server.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| The address does not load at all | Check Part D (both ports, TCP, `0.0.0.0/0`) and that DuckDNS shows the server's current IP. `curl -I http://localhost` on the server should answer. |
| Browser warns about the certificate | DNS was not ready when Caddy started: wait 1–2 minutes and reload, or run `sudo docker compose restart caddy`. |
| The build fails | Copy the last 40 lines of the output and fix or report them; run `sudo docker compose up -d --build` again (finished steps are reused). |
| "Out of capacity" when creating the server | See Part C. |
| Tertiary level says it was skipped | The Swiss-Model token is missing: edit `deploy/.env`, then `sudo docker compose up -d`. |
| `Permission denied (publickey)` when connecting | Use `-i` with the key file, user `ubuntu`, and `chmod 600` on the key. |
