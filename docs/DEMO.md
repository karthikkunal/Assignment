# Five-minute demonstration script

This is a word-for-word recording script for the QuantumGenie screening submission. Keep the terminal and browser side by side, use 125% browser zoom only if text is difficult to read, and trim dependency-download waiting time so the final video stays below five minutes.

## Before recording

Close unrelated windows and notifications. Open PowerShell in the repository root. If the app is already running, stop it with `Ctrl+C`. Keep [README.md](../README.md) open in a second editor tab for the architecture close.

The commands below assume the repository is located at:

```powershell
C:\Users\v-chkarthik\Downloads\Assignment
```

Change that path if the repository is elsewhere.

---

## 0:00-0:20 - Introduction

**On screen:** Show the repository root in VS Code with `agent`, `backend`, `frontend`, `scripts`, and `docs` visible.

**Say:**

> This is QuantumGenie Discovery, a local Windows product with a Go endpoint agent, FastAPI and SQLite backend, and React interface. I will set it up, run both discovery workflows, inspect their evidence, and finish with scheduling and safety.

---

## 0:20-0:55 - Reproducible setup and package size

**Run:**

```powershell
Set-Location "C:\Users\v-chkarthik\Downloads\Assignment"
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1
```

**Say while it runs:**

> `setup.ps1` creates the Python environment, installs the backend, runs `npm ci`, builds React, executes the test suites, compiles the stripped agent, and creates its ZIP. The execution-policy change applies only to this terminal.

**Recording note:** On a clean machine, package downloads can take several minutes. Keep the command and final successful output in the video, but speed up or trim the idle download interval.

**Run:**

```powershell
Get-Item .\agent\dist\quantumgenie-agent-windows-amd64.zip |
	Select-Object Name, Length
```

**Say:**

> The installable agent is 2.90 MiB, below the 5 MiB limit, which the build script enforces.

---

## 0:55-1:15 - Create safe demonstration evidence

**Run:**

```powershell
.\scripts\prepare-demo.ps1
```

**Say:**

> This creates two public files containing one certificate and exports no private key. I will scan the printed path to demonstrate fingerprint deduplication without hiding either location.

**On screen:** Keep the printed `ScanRoot`, normally `...\data\demo-certs`, visible for the next step.

---

## 1:15-1:35 - Start all local components

**Run:**

```powershell
.\scripts\start.ps1
```

**Say while startup messages appear:**

> `start.ps1` launches the agent on loopback port 8766 and the web API on 8765. The backend serves React, migrates SQLite, restores schedules, and creates a fresh shared command token.

**On screen:** Wait for both messages:

```text
agent listening ... 127.0.0.1:8766
Uvicorn running on http://127.0.0.1:8765
```

Open **http://127.0.0.1:8765**.

**Say:**

> The header shows component health, and this page retains every run and its evidence totals.

---

## 1:35-2:15 - Manual filesystem certificate scan

**On screen:** Select **Filesystem scan**. Paste the `ScanRoot` printed by `prepare-demo.ps1`, then select **Start scan**.

**Say:**

> The backend persists a queued run, sends its ID and root to the agent, then records running status. The agent reads files without modifying them, avoids symlinks, bounds reads, parses X.509 metadata, and fingerprints certificate DER.

**On screen:** The app navigates to **File System Scan Report**. Point to the status and four metrics.

**Say:**

> Two locations resolve to one unique certificate, proving SHA-256 deduplication while retaining both observations. The report exposes validity, algorithms, key size, issuer, location, parsing state, paths, and fingerprints.

**On screen:** Type `contoso` in the search field, then clear it. Scroll to **Certificate relationships** and point to the weighted host-to-certificate edge.

**Say:**

> Filters use retained evidence, and the weighted host-to-certificate edge represents both observations.

---

## 2:15-3:10 - Manual TLS metadata scan

**On screen:** Select **TLS scan** in the header. Enter:

```text
example.com:443
```

Set the duration to `3` seconds and select **Start scan**.

**Say:**

> This is metadata-only. The agent samples Windows connection ownership and performs an authorized handshake to the explicit target, recording SNI, protocol, cipher, and public peer certificate. It sends no application payload, decrypts nothing, and collects no credentials or private keys.

**On screen:** When **TLS Metadata Scan Report** loads, point to Events observed, Remote endpoints, Peer certificates, and Relationships. Then point to a successful active-probe row.

**Say:**

> Event counts and capture methods explain every total. This active-probe row shows endpoint, direction, process, handshake, protocol, cipher, and certificate fingerprint. Passive Windows rows mark handshake-only fields unavailable.

**On screen:** Briefly show the TLS versions, cipher suites, top endpoints, certificate posture, and activity charts. Scroll to **Relationship map**.

**Say:**

> The graph connects host, process, endpoint, service, and certificate; repetition increases edge weights.

---

## 3:10-3:45 - Run history, filters, and evidence states

**On screen:** Select **Discovery Runs** or the QuantumGenie logo. Use the type filter to select **TLS metadata**, then return it to **All types**. Search for the first characters of a run ID.

**Say:**

> SQLite retains trigger, timing, duration, records, and errors. The UI explicitly represents loading, running, completed, partial, failed, empty, and unavailable states rather than substituting mock data.

---

## 3:45-4:25 - Periodic scheduling

**On screen:** Select the calendar icon. Create this schedule:

```text
Name: Demo TLS schedule
Type: TLS metadata
Interval: 60 minutes
Target: example.com:443
Duration: 3 seconds
```

Select **Create schedule**.

**Say:**

> SQLite and APScheduler persist and restore this interval. The next run appears immediately, and executions use the same agent workflow with a Scheduled trigger.

**On screen:** Point to the next-run timestamp. Pause the schedule, resume it, and then delete it so it does not affect later demonstrations.

**Say:**

> Schedules can be paused, resumed, or removed without account management, which is out of scope.

---

## 4:25-4:52 - Architecture, permissions, and safety

**On screen:** Switch to the architecture diagram in [README.md](../README.md).

**Say:**

> FastAPI owns lifecycle, validation, scheduling, reports, and SQLite, while the independent Go agent returns structured evidence over loopback. Standard-user access is enough for normal roots and probes. Protected paths may require Administrator rights; failures remain visible, and the app never elevates itself.

---

## 4:52-5:00 - Close

**On screen:** Show the earlier green setup/test output, or use a second terminal with:

```powershell
.\scripts\test.ps1
```

**Say:**

> Automated Go, integration, scheduling, lint, TypeScript, and production-build checks pass. This completes the local workflow from installation to retained relationship evidence.

Stop there. The final narration is designed to finish just under five minutes at a clear speaking pace.

## Command reference for the presenter

```powershell
# Enter the repository
Set-Location "C:\Users\v-chkarthik\Downloads\Assignment"

# Permit local scripts only in this terminal
Set-ExecutionPolicy -Scope Process Bypass

# Install, build, test, and package
.\scripts\setup.ps1

# Show package size
Get-Item .\agent\dist\quantumgenie-agent-windows-amd64.zip |
	Select-Object Name, Length

# Generate public-only certificate evidence
.\scripts\prepare-demo.ps1

# Start agent, API, scheduler, database, and web UI
.\scripts\start.ps1

# Re-run all automated checks when needed
.\scripts\test.ps1
```

## Recovery lines if something goes wrong

- **Agent indicator is red:** say, "The API reports the agent as unavailable instead of hiding the failure." Return to the terminal, stop with `Ctrl+C`, and rerun `.\scripts\start.ps1`.
- **Port already in use:** run `.\scripts\start.ps1 -ApiPort 8875 -AgentPort 8876`, then open `http://127.0.0.1:8875`.
- **Filesystem report is empty:** confirm the dialog contains the exact `ScanRoot` printed by `.\scripts\prepare-demo.ps1`.
- **TLS target is unavailable:** use another host you are authorized to contact on port 443 and explain that failed handshakes are retained with their error evidence.
- **Setup downloads are slow:** trim only the waiting interval; keep the command, explanation, and final PASS output in the submitted video.