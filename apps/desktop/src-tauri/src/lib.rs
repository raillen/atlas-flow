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
    match env::var("ATLAS_FLOW_BACKEND_CMD") {
        Ok(raw) if !raw.trim().is_empty() => raw.split_whitespace().map(str::to_string).collect(),
        _ => DEFAULT_BACKEND_COMMAND
            .iter()
            .map(|s| s.to_string())
            .collect(),
    }
}

/// The directory the backend runs in: the project Atlas Flow is operating on.
fn project_root_path() -> PathBuf {
    if let Ok(root) = env::var("ATLAS_FLOW_PROJECT_ROOT") {
        return PathBuf::from(root);
    }
    let mut current = env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    loop {
        if current.join("PROJECT_MANIFEST.yaml").is_file() {
            return current;
        }
        match current.parent() {
            Some(parent) => current = parent.to_path_buf(),
            None => return env::current_dir().unwrap_or_else(|_| PathBuf::from(".")),
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
