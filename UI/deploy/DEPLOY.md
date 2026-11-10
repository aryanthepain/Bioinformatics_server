# Deploying the Protein Function Predictor

The whole app (website, API and all four structural levels) runs as one Docker
container on a cloud server, behind Caddy, which provides HTTPS automatically.

| What | Why |
| --- | --- |
| A Linux server with about **8 GB of memory** and **50 GB of disk** (e.g. Google Cloud `e2-standard-2`, free with the $300 trial) | ESM-2, the secondary-structure models and DIAMOND need about 4 GB of memory; Swiss-Prot, Pfam and the models need about 10 GB of disk. The server must stay on while analyses run. Free "platform" hosts (512 MB) are too small. |
| A web address, e.g. a free **DuckDNS** subdomain or your own domain | Caddy gets a free HTTPS certificate for it. |
| This `deploy/` folder | `Dockerfile` (builds everything), `docker-compose.yml` + `Caddyfile` (app + HTTPS), `setup_server.sh` (one-time server setup). |

The first build takes 30–40 minutes; updates take a few minutes.

---

## 1. Create the server (Google Cloud)

1. <https://cloud.google.com/free> → start the free trial (individual account).
2. **Compute Engine → VM instances → Create instance**:
   * name `protfunc`, region **asia-south1 (Mumbai)**;
   * machine type **e2-standard-2** (2 vCPU, 8 GB);
   * boot disk **Ubuntu 24.04 LTS (x86/64)**, **Balanced**, **50 GB**;
   * tick **Allow HTTP traffic** and **Allow HTTPS traffic** → **Create**.
3. **VPC network → IP addresses** → promote the VM's external IP to **static**.

(Any Ubuntu server with similar resources works the same way, e.g. Oracle
Cloud or Azure; open ports 80 and 443 in that provider's firewall.)

## 2. Web address

<https://www.duckdns.org> → add a subdomain → enter the server's IP → **update ip**.
With your own domain, add **A records** for `@` and `www` pointing to the IP.

## 3. Install and start the app (on the server)

Open a terminal on the server (Google Cloud: the **SSH** button), then:

```bash
tmux new -s deploy                      # keeps running if the connection drops
sudo apt-get update && sudo apt-get install -y git gh
gh auth login                           # GitHub.com → HTTPS → Yes → web browser
gh repo clone OWNER/REPO
cd REPO/UI/deploy
bash setup_server.sh
```

The script opens the web ports, installs Docker, asks for the web address and a
contact e-mail for EMBL-EBI (saved in `deploy/.env`, never
committed), then builds and starts everything. Reconnect later with `tmux attach -t deploy`.

## 4. Before a demo: pre-compute the examples

New sequences take a few minutes in total (mostly the web services: AlphaFold DB, Foldseek and, if enabled, EMBL-EBI), although
the results page opens as soon as the first level has finished (usually the primary
level, after about a minute), with a provisional prediction.
To make the examples open instantly, analyse them once (run from `REPO/UI/deploy`):

```bash
sudo docker compose exec app python scripts/precompute.py http://127.0.0.1:8000
```

It prints progress and takes roughly 10–30 minutes for the five examples. The
results are saved on the server and survive restarts and updates.

## 5. Updating after a change

Commit and push from your computer, then on the server:

```bash
cd ~/REPO && git pull
cd UI/deploy && sudo docker compose up -d --build
sudo docker image prune -f        # removes the old image to free disk space
```

## 6. Settings (`deploy/.env`)

| Setting | Effect |
| --- | --- |
| `SITE_ADDRESS` | The web address(es), comma-separated, e.g. `protfunc.duckdns.org, www.example.com` |
| `PFP_EBI_EMAIL` | Contact e-mail sent with the primary level's optional EMBL-EBI jobs (BLASTp, InterProScan), which EBI requires; they then run in the background after the local result. Empty: those two are skipped, as in the notebook's default fast local profile |
| `PFP_EBI_BLAST_TIMEOUT`, `PFP_EBI_INTERPRO_TIMEOUT` | Longest each EBI job may take, in seconds (defaults 1800 and 3600) |
| `PFP_QUICK_RESULT_SECONDS` | Seconds to wait for the quaternary level before the provisional prediction is shown (default 0: as soon as the primary level is done) |
| `PFP_PLACEHOLDER_LEVELS` | Use placeholder data for a level whose web service is down, e.g. `tertiary` |

After editing: `sudo docker compose up -d`.

## Useful commands (in `REPO/UI/deploy`)

| Task | Command |
| --- | --- |
| Status | `sudo docker compose ps` |
| App log (Ctrl+C stops following) | `sudo docker compose logs -f app` |
| Restart the app | `sudo docker compose restart app` |
| Stop / start everything | `sudo docker compose down` / `sudo docker compose up -d` |

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| The address does not load | Check that ports 80 and 443 are open in the provider's firewall and that the DNS record shows the server's current IP (`getent hosts <address>` on the server). |
| Browser warns about the certificate | DNS was not ready when Caddy started: wait a minute and reload, or `sudo docker compose restart caddy`. |
| The build fails | Copy the last 40 lines of the output; run `sudo docker compose up -d --build` again after fixing (finished steps are reused). |
| Browser terminal says "Connection failed" during the build | The server is busy; wait a few minutes and retry, then `tmux attach -t deploy`. |
| Tertiary level says it was skipped | It needs the primary level's closest Swiss-Prot match with an AlphaFold DB model; the message says which was missing. |
