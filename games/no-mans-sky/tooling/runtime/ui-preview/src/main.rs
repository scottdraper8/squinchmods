//! Standalone development host for the production overlay UI.
use search_probes_model::{
    address::{Address, Coordinates},
    cache::{CachedMatch, FaunaMatch},
    controls::Controls,
    fauna::{Domain, NameIdentity},
    runtime::{Action, Availability, State},
    settings::Settings,
    target::TargetKind,
};
use search_probes_ui::{App, ExportRequest, egui};
use std::{ffi::OsString, fs, path::PathBuf, process::Command, sync::Arc, time::Duration};

const SETTINGS_KEY: &str = "preview_settings";
const MAX_FIXTURES: usize = 100_000;

fn address(index: usize, planet: u8) -> Address {
    let system = u16::try_from(index % 4_095 + 1).expect("bounded preview fixture system");
    let x = i16::try_from(index / 4_095).expect("bounded preview fixture region") - 12;
    Address::new(Coordinates {
        x,
        y: 7,
        z: 24,
        galaxy: 0,
        system,
        planet,
    })
    .expect("preview fixture address")
}

fn destination(
    index: usize,
    planet: u8,
    kind: TargetKind,
    name: &str,
    fauna: Option<(Domain, bool)>,
) -> CachedMatch {
    let ordinal = index + 1;
    CachedMatch {
        address: address(index, planet),
        kind,
        system_name: Some(format!("Fixture System {ordinal}").into()),
        planet_name: (kind != TargetKind::System)
            .then(|| format!("Fixture Planet {ordinal}").into()),
        fauna: fauna.map(|(domain, cave)| FaunaMatch {
            role: (index % 30) as u8,
            name_identity: NameIdentity {
                species_seed: ordinal as u64,
                genus_seed: ordinal as u64 + 100,
            },
            name: Some(format!("{name} {ordinal}").into()),
            domain,
            cave,
        }),
    }
}

fn sample_results(count: usize) -> Vec<CachedMatch> {
    (0..count)
        .map(|index| match index % 10 {
            0 => destination(index, 0, TargetKind::System, "", None),
            1 => destination(index, 1, TargetKind::Planet, "", None),
            2 => destination(
                index,
                1,
                TargetKind::Fauna,
                "Surface Grazer",
                Some((Domain::Land, false)),
            ),
            3 => destination(
                index,
                2,
                TargetKind::Fauna,
                "Cave Burrower",
                Some((Domain::Land, true)),
            ),
            4 => destination(
                index,
                1,
                TargetKind::Fauna,
                "Highland Ray",
                Some((Domain::Airborne, false)),
            ),
            5 => destination(
                index,
                3,
                TargetKind::Fauna,
                "Reef Drifter",
                Some((Domain::Aquatic, false)),
            ),
            6 => destination(index, 1, TargetKind::Planet, "", None),
            7 => destination(index, 0, TargetKind::System, "", None),
            8 => destination(index, 4, TargetKind::Planet, "", None),
            _ => destination(index, 2, TargetKind::Planet, "", None),
        })
        .collect()
}

#[derive(Default)]
struct Options {
    reload_marker: Option<PathBuf>,
    fixtures: usize,
}

fn arguments(values: impl IntoIterator<Item = OsString>) -> Result<Options, String> {
    let mut values = values.into_iter();
    let mut options = Options::default();
    let mut fixtures_seen = false;
    while let Some(flag) = values.next() {
        match flag.to_str() {
            Some("--reload-marker") if options.reload_marker.is_none() => {
                options.reload_marker = Some(PathBuf::from(
                    values.next().ok_or("--reload-marker needs a path")?,
                ));
            }
            Some("--fixtures") if !fixtures_seen => {
                fixtures_seen = true;
                let value = values
                    .next()
                    .and_then(|value| value.into_string().ok())
                    .ok_or("--fixtures needs a non-negative integer")?;
                options.fixtures = value
                    .parse()
                    .map_err(|_| "--fixtures needs a non-negative integer")?;
                if options.fixtures > MAX_FIXTURES {
                    return Err(format!("--fixtures cannot exceed {MAX_FIXTURES}"));
                }
            }
            _ => {
                return Err(format!(
                    "unexpected preview argument: {}",
                    flag.to_string_lossy()
                ));
            }
        }
    }
    Ok(options)
}

fn save_export(request: &ExportRequest) -> Result<Option<String>, String> {
    let suggested = std::env::var_os("HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from("."))
        .join(request.suggested_name());
    let filter = match request.format.extension() {
        "txt" => "Text files (*.txt) | *.txt",
        "csv" => "CSV files (*.csv) | *.csv",
        _ => return Err("unsupported export format".into()),
    };
    let output = Command::new("zenity")
        .arg("--file-selection")
        .arg("--save")
        .arg("--confirm-overwrite")
        .arg("--title=Export Search Probes results")
        .arg(format!("--filename={}", suggested.display()))
        .arg(format!("--file-filter={filter}"))
        .output()
        .map_err(|error| format!("cannot open the preview save dialog: {error}"))?;
    if !output.status.success() {
        return if output.status.code() == Some(1) {
            Ok(None)
        } else {
            Err(format!(
                "preview save dialog failed: {}",
                String::from_utf8_lossy(&output.stderr).trim()
            ))
        };
    }
    let path = PathBuf::from(String::from_utf8_lossy(&output.stdout).trim());
    if path.as_os_str().is_empty() {
        return Err("preview save dialog returned an empty path".into());
    }
    fs::write(&path, request.contents.as_bytes())
        .map_err(|error| format!("cannot write {}: {error}", path.display()))?;
    Ok(Some(path.display().to_string()))
}

struct Preview {
    app: App,
    controls: Arc<Controls>,
    command_directory: PathBuf,
    reload_marker: Option<PathBuf>,
    announced: bool,
}

impl Preview {
    fn new(
        cc: &eframe::CreationContext<'_>,
        reload_marker: Option<PathBuf>,
        fixtures: usize,
    ) -> std::io::Result<Self> {
        let settings = cc
            .storage
            .and_then(|storage| eframe::get_value::<Settings>(storage, SETTINGS_KEY))
            .filter(|settings| settings.validate().is_ok())
            .unwrap_or_default();
        let mut state = State::new(settings);
        state.availability = if fixtures == 0 {
            Availability::MainMenu
        } else {
            Availability::Ready
        };
        if fixtures > 0 {
            state.player = Some(address(0, 0));
            state.results = sample_results(fixtures);
        }
        let controls = Arc::new(Controls::new(state));
        // Preview commands use their own ephemeral directory, never the installed mod's settings.
        let stamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map_err(std::io::Error::other)?
            .as_nanos();
        let command_directory = std::env::temp_dir().join(format!(
            "search-probes-preview-commands-{}-{stamp}",
            std::process::id()
        ));
        std::fs::create_dir(&command_directory)?;
        Ok(Self {
            app: App::new(&cc.egui_ctx, controls.clone()),
            controls,
            command_directory,
            reload_marker,
            announced: false,
        })
    }
}

impl eframe::App for Preview {
    fn logic(&mut self, ctx: &egui::Context, _: &mut eframe::Frame) {
        if self
            .reload_marker
            .as_ref()
            .is_some_and(|path| path.exists())
        {
            ctx.send_viewport_cmd(egui::ViewportCommand::Close);
        }
        // Check reload requests even when no input arrives or the window is hidden.
        ctx.request_repaint_after(Duration::from_millis(250));
    }

    fn ui(&mut self, ui: &mut egui::Ui, _: &mut eframe::Frame) {
        self.app.refresh();
        self.app.ui(ui);
        if let Some(request) = self.app.take_export_request() {
            self.app.finish_export(save_export(&request));
            ui.ctx().request_repaint();
        }
        self.controls.prepare(&self.command_directory);
        while let Some(command) = self.controls.pop() {
            self.controls.update(|state| {
                match command.action {
                    Action::Configure { settings } => state.settings = settings,
                    _ => state.error = Some("Searching and navigation run in NMS.".into()),
                }
                state.last_command = command.id;
            });
            ui.ctx().request_repaint();
        }
        if !self.announced {
            println!(
                "Search Probes UI preview rendered (PID {}).",
                std::process::id()
            );
            self.announced = true;
        }
    }

    fn save(&mut self, storage: &mut dyn eframe::Storage) {
        eframe::set_value(storage, SETTINGS_KEY, self.app.settings());
    }
}

impl Drop for Preview {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.command_directory);
    }
}

fn main() -> eframe::Result {
    let arguments = arguments(std::env::args_os().skip(1)).unwrap_or_else(|error| {
        eprintln!("{error}\nusage: preview [--reload-marker PATH] [--fixtures COUNT]");
        std::process::exit(2);
    });
    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_app_id("search-probes-ui-preview")
            .with_inner_size([1800.0, 1100.0])
            .with_min_inner_size([420.0, 300.0]),
        renderer: eframe::Renderer::Glow,
        ..Default::default()
    };
    eframe::run_native(
        "Search Probes — UI Preview",
        options,
        Box::new(move |cc| {
            Ok(Box::new(Preview::new(
                cc,
                arguments.reload_marker,
                arguments.fixtures,
            )?))
        }),
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fixtures_are_optional_and_counted_from_the_cli() {
        assert_eq!(arguments([]).unwrap().fixtures, 0);
        assert_eq!(
            arguments([OsString::from("--fixtures"), OsString::from("23")])
                .unwrap()
                .fixtures,
            23
        );
        assert!(arguments([OsString::from("--fixtures")]).is_err());
    }

    #[test]
    fn requested_fixtures_repeat_the_patterns_with_unique_destinations() {
        let results = sample_results(23);
        assert_eq!(results.len(), 23);
        for (index, result) in results.iter().enumerate() {
            assert!(
                results[..index]
                    .iter()
                    .all(|previous| previous.target() != result.target())
            );
        }
        assert!(
            results
                .iter()
                .filter_map(|result| result.fauna.as_ref())
                .any(|fauna| fauna.domain == Domain::Land && fauna.cave)
        );
    }
}
