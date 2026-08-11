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
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;

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

/// The directory the backend runs in: the project Atlas Flow is operating on.
fn project_root_path() -> PathBuf {
    let start = env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    resolve_project_root(env::var("ATLAS_FLOW_PROJECT_ROOT").ok().as_deref(), &start)
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

    let child = Command::new(program)
        .args(args)
        .current_dir(project_root_path())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|error| format!("could not start {program}: {error}"))?;

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
