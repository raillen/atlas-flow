//! Atlas Flow desktop shell.
//!
//! Orchestration lives in the Python backend. This crate owns three things the
//! browser cannot do for itself: the window, where the project root is, and the
//! lifetime of the backend process.
//!
//! The backend is started and stopped through explicit commands rather than
//! being spawned at launch, so a developer already running `uvicorn` by hand
//! keeps that process instead of racing a second one for the port.

use std::env;
use std::fs::File;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::Duration;

use serde::Serialize;
use tauri::{Manager, RunEvent, State};

/// Where the frontend talks to the backend. Overridable so a packaged build can
/// point at a backend on another port without being rebuilt.
const DEFAULT_BACKEND_URL: &str = "http://localhost:8000";

const DEFAULT_BACKEND_COMMAND: &[&str] = &[
    "uv",
    "run",
    "--project",
    "backend",
    "uvicorn",
    "atlas_flow.api.app:create_app",
    "--factory",
    "--port",
    "8000",
];

#[derive(Default)]
struct Backend(Mutex<Option<Child>>);

#[derive(Serialize)]
struct BackendStatus {
    running: bool,
    url: String,
    command: Vec<String>,
    project_root: String,
    log_path: String,
}

/// Where a backend this shell started writes its output.
///
/// Discarding it was a mistake worth naming: a backend that dies on startup —
/// a broken virtualenv, a port already taken — then leaves nothing to read,
/// and the window shows a connection error that blames the wrong thing.
fn backend_log_path() -> PathBuf {
    env::temp_dir().join("atlas-flow-backend.log")
}

fn backend_url() -> String {
    env::var("ATLAS_FLOW_API").unwrap_or_else(|_| DEFAULT_BACKEND_URL.to_string())
}

fn backend_command() -> Vec<String> {
    parse_backend_command(env::var("ATLAS_FLOW_BACKEND_CMD").ok().as_deref())
}

/// The environment reading is separated from the decision so the decision can
/// be tested: `env::set_var` is process-global, and Rust runs tests in threads.
fn parse_backend_command(raw: Option<&str>) -> Vec<String> {
    match raw {
        Some(value) if !value.trim().is_empty() => {
            value.split_whitespace().map(str::to_string).collect()
        }
        _ => DEFAULT_BACKEND_COMMAND
            .iter()
            .map(|s| s.to_string())
            .collect(),
    }
}

/// Where this application was unpacked, when it is running from a bundle.
///
/// AppImages export APPDIR and run with their working directory inside their
/// own mount, so a packaged build that trusts the working directory ends up
/// searching *itself* for a project.
fn bundle_dir() -> Option<PathBuf> {
    env::var("APPDIR")
        .ok()
        .filter(|value| !value.is_empty())
        .map(PathBuf::from)
}

/// The directory the backend runs in: the project Atlas Flow is operating on.
///
/// Empty means no project could be determined, which is a state the caller has
/// to handle rather than paper over: launching a backend in the wrong
/// directory produces a run with no Goals and an error that blames the backend.
fn project_root_path() -> PathBuf {
    // OWD is the directory an AppImage was launched from, when it sets it at
    // all; the process working directory is the fallback.
    let start = env::var("OWD")
        .map(PathBuf::from)
        .or_else(|_| env::current_dir())
        .unwrap_or_else(|_| PathBuf::from("."));
    let resolved =
        resolve_project_root(env::var("ATLAS_FLOW_PROJECT_ROOT").ok().as_deref(), &start);

    if let Some(bundle) = bundle_dir()
        && resolved.starts_with(&bundle)
    {
        return PathBuf::new();
    }
    resolved
}

/// Strip the bundle's own runtime out of a child process's environment.
///
/// An AppImage points PYTHONHOME, LD_LIBRARY_PATH and a dozen GTK variables at
/// itself so the bundled application works. A backend launched from inside
/// inherits all of it and dies on startup complaining about Python paths that
/// have nothing to do with the real problem. Everything mentioning the bundle
/// is removed, rather than a hand-kept list of names that would drift.
fn strip_bundle_environment(command: &mut Command) {
    let Some(bundle) = bundle_dir() else { return };
    let plan = bundle_environment_plan(env::vars(), &bundle.to_string_lossy());

    for name in plan.remove {
        command.env_remove(name);
    }
    if let Some(path) = plan.path {
        command.env("PATH", path);
    }
}

/// What to change about a child's environment, decided without touching one.
#[derive(Debug, Default, PartialEq)]
struct EnvironmentPlan {
    remove: Vec<String>,
    path: Option<String>,
}

/// Every variable naming the bundle is dropped; PATH keeps everything else.
///
/// Deciding by value rather than by a list of variable names means the rule
/// does not drift as the bundler adds variables. Keeping it a pure function is
/// what makes it testable at all: `env::set_var` is process-global and Rust
/// runs tests in threads, so a test that set the environment would be testing
/// the other tests too.
fn bundle_environment_plan<I>(vars: I, bundle: &str) -> EnvironmentPlan
where
    I: IntoIterator<Item = (String, String)>,
{
    let mut plan = EnvironmentPlan::default();
    if bundle.is_empty() {
        return plan;
    }

    for (name, value) in vars {
        if !value.contains(bundle) {
            continue;
        }
        if name == "PATH" {
            // PATH is needed; only its bundle entries are not.
            let kept: Vec<&str> = value
                .split(':')
                .filter(|entry| !entry.contains(bundle))
                .collect();
            plan.path = Some(kept.join(":"));
        } else {
            plan.remove.push(name);
        }
    }
    plan
}

/// Spawn, then confirm it is still alive before calling it started.
///
/// Spawning succeeds for a command that dies immediately, so a status reported
/// the instant after spawn is not a status. A backend that exited on startup
/// comes back as an error naming the exit code and the last words of its log,
/// rather than as a running service the user then watches fail to answer.
fn spawn_and_confirm(command: &mut Command, log: &Path) -> Result<Child, String> {
    let mut child = command
        .spawn()
        .map_err(|error| format!("could not start the backend: {error}"))?;

    std::thread::sleep(Duration::from_millis(400));
    match child.try_wait() {
        Ok(Some(status)) => {
            let tail = std::fs::read_to_string(log).unwrap_or_default();
            let reason = tail.lines().rev().take(3).collect::<Vec<_>>().join(" / ");
            Err(format!(
                "the backend exited immediately ({status}). See {}: {reason}",
                log.display()
            ))
        }
        _ => Ok(child),
    }
}

/// The nearest ancestor of `start` holding a project manifest, unless an
/// explicit override says otherwise. Never this crate's own source tree: an
/// installed shell must not serve its own project to somebody else's.
fn resolve_project_root(override_root: Option<&str>, start: &std::path::Path) -> PathBuf {
    if let Some(root) = override_root
        && !root.trim().is_empty()
    {
        return PathBuf::from(root);
    }
    let mut current = start.to_path_buf();
    loop {
        if current.join("PROJECT_MANIFEST.yaml").is_file() {
            return current;
        }
        match current.parent() {
            Some(parent) => current = parent.to_path_buf(),
            None => return start.to_path_buf(),
        }
    }
}

/// True only if the child is still alive. A process that exited on its own must
/// not be reported as running, or "stop" would have nothing to stop and "start"
/// would refuse to help.
fn is_alive(slot: &mut Option<Child>) -> bool {
    match slot {
        Some(child) => match child.try_wait() {
            Ok(Some(_)) => {
                *slot = None;
                false
            }
            Ok(None) => true,
            Err(_) => {
                *slot = None;
                false
            }
        },
        None => false,
    }
}

fn status_of(running: bool) -> BackendStatus {
    BackendStatus {
        running,
        url: backend_url(),
        command: backend_command(),
        project_root: project_root_path().to_string_lossy().to_string(),
        log_path: backend_log_path().to_string_lossy().to_string(),
    }
}

#[tauri::command]
fn backend_status(backend: State<'_, Backend>) -> BackendStatus {
    let mut slot = backend.0.lock().expect("backend lock");
    status_of(is_alive(&mut slot))
}

#[tauri::command]
fn start_backend(backend: State<'_, Backend>) -> Result<BackendStatus, String> {
    let mut slot = backend.0.lock().expect("backend lock");
    if is_alive(&mut slot) {
        return Ok(status_of(true));
    }

    let argv = backend_command();
    let (program, args) = argv.split_first().ok_or("empty backend command")?;

    let log = backend_log_path();
    let out =
        File::create(&log).map_err(|error| format!("could not open {}: {error}", log.display()))?;
    let err = out
        .try_clone()
        .map_err(|error| format!("could not open {}: {error}", log.display()))?;

    let root = project_root_path();
    if root.as_os_str().is_empty() {
        return Err(
            "No project selected. Launch Atlas Flow from a project directory, or set \
             ATLAS_FLOW_PROJECT_ROOT to one."
                .to_string(),
        );
    }

    let mut command = Command::new(program);
    command
        .args(args)
        .current_dir(&root)
        .stdout(Stdio::from(out))
        .stderr(Stdio::from(err));
    strip_bundle_environment(&mut command);

    let child = spawn_and_confirm(&mut command, &log)?;

    *slot = Some(child);
    Ok(status_of(true))
}

#[tauri::command]
fn stop_backend(backend: State<'_, Backend>) -> Result<BackendStatus, String> {
    let mut slot = backend.0.lock().expect("backend lock");
    if let Some(mut child) = slot.take() {
        child.kill().map_err(|error| error.to_string())?;
        let _ = child.wait();
    }
    Ok(status_of(false))
}

#[tauri::command]
fn project_root() -> String {
    project_root_path().to_string_lossy().to_string()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(Backend::default())
        .invoke_handler(tauri::generate_handler![
            backend_status,
            start_backend,
            stop_backend,
            project_root
        ])
        .build(tauri::generate_context!())
        .expect("error launching Atlas Flow");

    app.run(|handle, event| {
        // A backend this shell started is this shell's responsibility. Leaving
        // it holding the port after the window closes is how the next launch
        // fails for no visible reason.
        if let RunEvent::Exit = event
            && let Some(backend) = handle.try_state::<Backend>()
        {
            let mut slot = backend.0.lock().expect("backend lock");
            if let Some(mut child) = slot.take() {
                let _ = child.kill();
                let _ = child.wait();
            }
        }
    });
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    #[test]
    fn an_unset_command_falls_back_to_the_default() {
        assert_eq!(parse_backend_command(None), DEFAULT_BACKEND_COMMAND);
    }

    #[test]
    fn a_blank_command_is_treated_as_unset() {
        // An empty variable is somebody clearing it, not asking to run "".
        assert_eq!(parse_backend_command(Some("   ")), DEFAULT_BACKEND_COMMAND);
    }

    #[test]
    fn a_configured_command_is_split_into_argv() {
        assert_eq!(
            parse_backend_command(Some("python -m uvicorn app:make --port 9000")),
            vec!["python", "-m", "uvicorn", "app:make", "--port", "9000"]
        );
    }

    #[test]
    fn the_override_wins_over_any_search() {
        let root = resolve_project_root(Some("/srv/atlas"), std::path::Path::new("/tmp"));
        assert_eq!(root, PathBuf::from("/srv/atlas"));
    }

    #[test]
    fn a_blank_override_is_ignored() {
        let temp = std::env::temp_dir().join("atlas-blank-override");
        fs::create_dir_all(&temp).unwrap();
        assert_eq!(resolve_project_root(Some(""), &temp), temp);
    }

    #[test]
    fn the_nearest_ancestor_with_a_manifest_wins() {
        let base = std::env::temp_dir().join("atlas-root-search");
        let nested = base.join("packages").join("api");
        fs::create_dir_all(&nested).unwrap();
        fs::write(base.join("PROJECT_MANIFEST.yaml"), "project:\n  id: x\n").unwrap();

        assert_eq!(resolve_project_root(None, &nested), base);

        fs::remove_dir_all(&base).unwrap();
    }

    #[test]
    fn a_launch_directory_is_searched_rather_than_the_bundle() {
        // Regression: an AppImage runs with its working directory inside its
        // own mount, so resolving from current_dir() made the packaged app
        // search itself and report /tmp/.mount_*/usr as the project root.
        let base = std::env::temp_dir().join("atlas-owd-search");
        let launched_from = base.join("apps").join("desktop");
        fs::create_dir_all(&launched_from).unwrap();
        fs::write(base.join("PROJECT_MANIFEST.yaml"), "project:\n  id: x\n").unwrap();

        assert_eq!(resolve_project_root(None, &launched_from), base);

        fs::remove_dir_all(&base).unwrap();
    }

    #[test]
    fn a_directory_with_no_manifest_anywhere_above_stays_put() {
        let temp = std::env::temp_dir().join("atlas-no-manifest");
        fs::create_dir_all(&temp).unwrap();
        // Walking to / and finding nothing must not return "/" as the project.
        let resolved = resolve_project_root(None, &temp);
        assert!(resolved == temp || resolved.join("PROJECT_MANIFEST.yaml").is_file());
    }

    #[test]
    fn an_empty_slot_is_never_reported_as_running() {
        let mut slot: Option<Child> = None;
        assert!(!is_alive(&mut slot));
    }

    #[test]
    fn a_process_that_exited_is_forgotten_rather_than_reported_running() {
        // Otherwise "stop" has nothing to stop and "start" refuses to help.
        let child = Command::new(if cfg!(windows) { "cmd" } else { "true" })
            .args(if cfg!(windows) {
                vec!["/C", "exit"]
            } else {
                vec![]
            })
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn();
        let Ok(mut child) = child else { return };
        let _ = child.wait();

        let mut slot = Some(child);
        assert!(!is_alive(&mut slot));
        assert!(slot.is_none());
    }
}

#[cfg(test)]
mod bundle_tests {
    use super::*;

    fn vars(pairs: &[(&str, &str)]) -> Vec<(String, String)> {
        pairs
            .iter()
            .map(|(k, v)| ((*k).to_string(), (*v).to_string()))
            .collect()
    }

    #[test]
    fn outside_a_bundle_nothing_is_changed() {
        let plan = bundle_environment_plan(vars(&[("PYTHONHOME", "/usr")]), "");

        assert_eq!(plan, EnvironmentPlan::default());
    }

    #[test]
    fn every_variable_naming_the_bundle_is_dropped() {
        // Regression: an AppImage points PYTHONHOME and LD_LIBRARY_PATH at
        // itself, and the Python backend it launched inherited them and died
        // on a Python path error that named nothing real.
        let plan = bundle_environment_plan(
            vars(&[
                ("PYTHONHOME", "/tmp/.mount_x/usr"),
                ("LD_LIBRARY_PATH", "/tmp/.mount_x/usr/lib"),
                ("GTK_PATH", "/tmp/.mount_x/usr/lib/gtk-3.0"),
                ("HOME", "/home/someone"),
                ("LANG", "en_GB.UTF-8"),
            ]),
            "/tmp/.mount_x",
        );

        assert_eq!(
            plan.remove,
            vec!["PYTHONHOME", "LD_LIBRARY_PATH", "GTK_PATH"]
        );
        assert!(plan.path.is_none());
    }

    #[test]
    fn path_keeps_everything_except_its_bundle_entries() {
        // Removing PATH outright would leave the child unable to find
        // anything at all.
        let plan = bundle_environment_plan(
            vars(&[("PATH", "/tmp/.mount_x/usr/bin:/usr/local/bin:/usr/bin")]),
            "/tmp/.mount_x",
        );

        assert_eq!(plan.path.as_deref(), Some("/usr/local/bin:/usr/bin"));
        assert!(plan.remove.is_empty());
    }

    #[test]
    fn a_variable_that_merely_mentions_a_similar_path_is_left_alone() {
        let plan = bundle_environment_plan(
            vars(&[("EDITOR", "/tmp/.mounted-elsewhere/bin/vi")]),
            "/tmp/.mount_x",
        );

        assert!(plan.remove.is_empty());
    }

    #[test]
    fn a_command_that_dies_immediately_is_not_reported_as_started() {
        // Regression: start_backend returned RUNNING the instant after spawn,
        // so a backend that failed on startup was shown as healthy while every
        // panel reported a connection error, blaming the wrong component.
        let log = std::env::temp_dir().join("atlas-spawn-probe.log");
        std::fs::write(&log, "boom: could not import the application\n").unwrap();

        let mut command = Command::new(if cfg!(windows) { "cmd" } else { "false" });
        if cfg!(windows) {
            command.args(["/C", "exit 1"]);
        }
        command.stdout(Stdio::null()).stderr(Stdio::null());

        let result = spawn_and_confirm(&mut command, &log);

        let message = result.expect_err("a dead process must not look started");
        assert!(message.contains("exited immediately"), "{message}");
        // The reason the user needs is the log's last words, not the exit code.
        assert!(
            message.contains("could not import the application"),
            "{message}"
        );

        std::fs::remove_file(&log).ok();
    }

    #[test]
    fn a_command_that_keeps_running_is_reported_as_started() {
        let log = std::env::temp_dir().join("atlas-spawn-probe-alive.log");
        let mut command = Command::new(if cfg!(windows) { "timeout" } else { "sleep" });
        command.arg("5").stdout(Stdio::null()).stderr(Stdio::null());

        let mut child = spawn_and_confirm(&mut command, &log)
            .expect("a live process must be reported as started");

        let mut slot = Some(child.try_wait().map(|_| child).unwrap());
        assert!(is_alive(&mut slot));

        if let Some(mut running) = slot {
            let _ = running.kill();
            let _ = running.wait();
        }
    }
}
