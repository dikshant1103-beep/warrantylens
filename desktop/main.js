// WarrantyLens desktop shell.
// Starts the local engine (Docker stack) in the background, waits until the API
// is healthy, then shows the UI in a native window — no browser, no URL bar.
const { app, BrowserWindow, dialog, Menu } = require("electron");
const { execSync } = require("child_process");
const path = require("path");
const http = require("http");

// When packaged into an AppImage, __dirname is inside the bundle — point at the
// real project (which holds docker-compose.yml, build contexts, and models).
const PROJECT_ROOT =
  process.env.WARRANTYLENS_ROOT ||
  (app.isPackaged
    ? "/home/dikshant/Desktop/ev-warranty-inspection"
    : path.resolve(__dirname, ".."));
const API_HEALTH = "http://localhost:8000/api/v1/health";
const APP_URL = "http://localhost:3000";

let mainWin = null;
let splashWin = null;

// --- Docker access (direct, or via `sg docker` if the session lacks the group) ---
function dockerMode() {
  try {
    execSync("docker info", { stdio: "ignore" });
    return "direct";
  } catch {
    try {
      execSync('sg docker -c "docker info"', { stdio: "ignore" });
      return "sg";
    } catch {
      return "none";
    }
  }
}

function runCompose(args, mode) {
  const base = `docker compose ${args}`;
  const cmd = mode === "sg" ? `sg docker -c ${JSON.stringify(base)}` : base;
  execSync(cmd, { cwd: PROJECT_ROOT, stdio: "ignore" });
}

function setSplashStatus(text) {
  if (splashWin && !splashWin.isDestroyed()) {
    splashWin.webContents
      .executeJavaScript(`window.setStatus && window.setStatus(${JSON.stringify(text)});`)
      .catch(() => {});
  }
}

function waitForHealth(timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  return new Promise((resolve) => {
    const tick = () => {
      http
        .get(API_HEALTH, (res) => {
          res.resume();
          if (res.statusCode === 200) return resolve(true);
          retry();
        })
        .on("error", retry);
    };
    const retry = () => (Date.now() > deadline ? resolve(false) : setTimeout(tick, 2000));
    tick();
  });
}

function createSplash() {
  splashWin = new BrowserWindow({
    width: 520, height: 320, frame: false, resizable: false, center: true,
    backgroundColor: "#0f172a",
  });
  splashWin.loadFile(path.join(__dirname, "loading.html"));
}

function createMain() {
  mainWin = new BrowserWindow({
    width: 1440, height: 900, show: false, title: "WarrantyLens",
    backgroundColor: "#f8fafc",
    webPreferences: { contextIsolation: true },
  });
  Menu.setApplicationMenu(null); // no menu bar — feels like an app, not a browser
  mainWin.loadURL(APP_URL);
  mainWin.once("ready-to-show", () => {
    if (splashWin && !splashWin.isDestroyed()) splashWin.close();
    mainWin.show();
  });
}

function fatal(message) {
  setSplashStatus("⚠ " + message);
  dialog.showErrorBox("WarrantyLens", message);
}

async function boot() {
  createSplash();

  const mode = dockerMode();
  if (mode === "none") {
    return fatal(
      "Can't reach Docker. Install it (curl -fsSL https://get.docker.com | sudo sh) " +
        "or log out/in once after install, then relaunch."
    );
  }

  try {
    setSplashStatus("Starting the inspection engine…");
    runCompose("up -d", mode);
  } catch (e) {
    return fatal("Failed to start the engine.\n" + String(e).slice(0, 300));
  }

  setSplashStatus("Warming up services…");
  const healthy = await waitForHealth(180000);
  if (!healthy) return fatal("The engine did not become ready in time.");

  try {
    setSplashStatus("Preparing database…");
    runCompose("exec -T api alembic upgrade head", mode);
    runCompose("exec -T api python -m app.scripts.seed", mode);
  } catch {
    /* idempotent; ignore */
  }

  setSplashStatus("Opening WarrantyLens…");
  createMain();
}

app.whenReady().then(boot);

app.on("window-all-closed", () => {
  // Leave the engine running in the background for instant relaunch.
  app.quit();
});
