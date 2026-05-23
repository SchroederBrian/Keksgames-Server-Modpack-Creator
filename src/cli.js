#!/usr/bin/env node
import React, {useEffect, useMemo, useState} from 'react';
import {render, Box, Text, useApp, useInput, useWindowSize} from 'ink';
import {spawn, spawnSync} from 'node:child_process';
import {platform} from 'node:os';

const h = React.createElement;
const python = process.env.PYTHON || 'python';
const isInteractive = Boolean(process.stdin.isTTY);
const MIN_WIDTH = 80;
const MIN_HEIGHT = 24;

const palette = {
	accent: '#8fd3ff',
	gold: '#f4f0d9',
	muted: '#9aa7b7',
	panel: '#44546a',
	good: '#75d995',
	warn: '#ffd166',
	bad: '#ff7a90'
};

function backend(args, options = {}) {
	return spawn(python, ['-m', 'keksgames_server_modpack_creator.react_backend', ...args], {
		stdio: ['pipe', 'pipe', 'pipe'],
		...options
	});
}

function discoverDefaults() {
	const result = spawnSync(python, ['-m', 'keksgames_server_modpack_creator.react_backend', 'discover'], {
		encoding: 'utf8'
	});

	if (result.status !== 0) {
		throw new Error((result.stderr || result.stdout || 'Discovery failed').trim());
	}

	return JSON.parse(result.stdout);
}

function runJsonLines(args, {input, onEvent}) {
	return new Promise((resolve, reject) => {
		const child = backend(args);
		let stdout = '';
		let stderr = '';
		let settled = false;

		child.stdout.on('data', chunk => {
			stdout += chunk.toString();
			const lines = stdout.split(/\r?\n/);
			stdout = lines.pop() ?? '';
			for (const line of lines) {
				if (!line.trim()) {
					continue;
				}
				try {
					const event = JSON.parse(line);
					onEvent?.(event);
					if (event.type === 'result') {
						settled = true;
						resolve(event);
					}
				} catch (error) {
					reject(error);
				}
			}
		});

		child.stderr.on('data', chunk => {
			stderr += chunk.toString();
		});

		child.on('error', reject);
		child.on('close', code => {
			if (code !== 0) {
				reject(new Error(stderr.trim() || `Backend exited with ${code}`));
				return;
			}
			if (!settled) {
				reject(new Error('Backend finished without result.'));
			}
		});

		if (input) {
			child.stdin.write(JSON.stringify(input));
		}
		child.stdin.end();
	});
}

function openExternal(url) {
	if (!url) {
		return;
	}

	if (platform() === 'win32') {
		spawn('powershell', ['-NoProfile', '-Command', 'Start-Process -FilePath $args[0]', url], {detached: true, stdio: 'ignore'}).unref();
		return;
	}

	spawn(platform() === 'darwin' ? 'open' : 'xdg-open', [url], {detached: true, stdio: 'ignore'}).unref();
}

function openFolder(path) {
	if (!path) {
		return;
	}

	if (platform() === 'win32') {
		spawn('explorer.exe', [path], {detached: true, stdio: 'ignore'}).unref();
		return;
	}

	spawn(platform() === 'darwin' ? 'open' : 'xdg-open', [path], {detached: true, stdio: 'ignore'}).unref();
}

function App() {
	const {exit} = useApp();
	const windowSize = useWindowSize();
	const width = Math.max(MIN_WIDTH, windowSize.columns || MIN_WIDTH);
	const height = Math.max(MIN_HEIGHT, windowSize.rows || MIN_HEIGHT);
	const contentWidth = Math.max(40, width - 10);
	const profileVisibleRows = Math.max(3, height - 18);
	const logVisibleRows = Math.max(5, height - 8);
	const reportVisibleRows = Math.max(5, height - 9);
	const [defaults, setDefaults] = useState(null);
	const [screen, setScreen] = useState('loading');
	const [error, setError] = useState(null);
	const [focus, setFocus] = useState(0);
	const [profileIndex, setProfileIndex] = useState(0);
	const [profileOffset, setProfileOffset] = useState(0);
	const [modsPath, setModsPath] = useState('');
	const [outputPath, setOutputPath] = useState('');
	const [logs, setLogs] = useState([]);
	const [logOffset, setLogOffset] = useState(0);
	const [logFollowTail, setLogFollowTail] = useState(true);
	const [candidates, setCandidates] = useState([]);
	const [manualQueue, setManualQueue] = useState([]);
	const [manualIndex, setManualIndex] = useState(0);
	const [reportOffset, setReportOffset] = useState(0);

	useEffect(() => {
		try {
			const data = discoverDefaults();
			setDefaults(data);
			setModsPath(data.default_mods ?? '');
			setOutputPath(data.default_output ?? '');
			setScreen('setup');
		} catch (discoveryError) {
			setError(discoveryError.message);
			setScreen('error');
		}
	}, []);

	const startScan = () => {
		setScreen('scan');
		setLogs([]);
		setLogOffset(0);
		setLogFollowTail(true);
		setCandidates([]);
		setManualQueue([]);
		setManualIndex(0);
		runJsonLines(['scan', modsPath], {
			onEvent: event => {
				if (event.type === 'status') {
					setLogs(previous => [...previous, event.message]);
				}
				if (event.type === 'result') {
					setCandidates(event.candidates);
					const nextManualQueue = event.candidates.filter(needsManualDecision);
					setManualQueue(nextManualQueue);
					const needsManual = nextManualQueue.length > 0;
					setScreen(needsManual ? 'decision' : 'build');
				}
			}
		}).catch(scanError => {
			setError(scanError.message);
			setScreen('error');
		});
	};

	const startBuild = () => {
		setScreen('build');
		setLogOffset(0);
		setLogFollowTail(true);
		setLogs(previous => [...previous, `Build output: ${outputPath}`]);
		runJsonLines(['build', modsPath, outputPath], {
			input: candidates,
			onEvent: event => {
				if (event.type === 'status') {
					setLogs(previous => [...previous, event.message]);
				}
				if (event.type === 'result') {
					setScreen('report');
				}
			}
		}).catch(buildError => {
			setError(buildError.message);
			setScreen('error');
		});
	};

	const resetToSetup = () => {
		setScreen('setup');
		setLogs([]);
		setLogOffset(0);
		setLogFollowTail(true);
		setCandidates([]);
		setManualQueue([]);
		setManualIndex(0);
		setReportOffset(0);
		setFocus(0);
	};

	useEffect(() => {
		if (screen === 'build') {
			startBuild();
		}
		// startBuild intentionally captures the current candidates/output path.
		// eslint-disable-next-line react-hooks/exhaustive-deps
	}, [screen]);

	useInput((input, key) => {
		if (key.ctrl && input === 'c') {
			exit();
			return;
		}
		if (input === 'q' && screen !== 'scan' && screen !== 'build') {
			exit();
			return;
		}

		if (screen === 'setup') {
			handleSetupInput({input, key, defaults, focus, setFocus, profileIndex, setProfileIndex, profileOffset, setProfileOffset, profileVisibleRows, setModsPath, setOutputPath, startScan});
			return;
		}

		if (screen === 'scan' || screen === 'build') {
			handleLogInput({key, logs, logOffset, logVisibleRows, setLogOffset, setLogFollowTail});
			return;
		}

		if (screen === 'decision') {
			handleDecisionInput({
				input,
				manualQueue,
				manualIndex,
				setManualIndex,
				setCandidates,
				setScreen
			});
			return;
		}

		if (screen === 'report' && input === 'o') {
			openFolder(outputPath);
			return;
		}

		if (screen === 'report') {
			handleReportInput({input, key, candidates, reportOffset, reportVisibleRows, setReportOffset, resetToSetup});
		}
	}, {isActive: isInteractive});

	useEffect(() => {
		if (logFollowTail) {
			setLogOffset(Math.max(0, logs.length - logVisibleRows));
		}
	}, [logs, logFollowTail, logVisibleRows]);

	if (screen === 'loading') {
		return h(Frame, {width, height}, h(Text, {color: palette.accent}, 'Loading React TUI...'));
	}

	if (screen === 'error') {
		return h(Frame, {width, height},
			h(Text, {color: palette.bad}, 'Fehler'),
			h(Text, null, error),
			h(Text, {color: palette.muted}, 'q beendet.')
		);
	}

	if (screen === 'setup') {
		return h(SetupScreen, {defaults, modsPath, outputPath, focus, profileIndex, profileOffset, profileVisibleRows, width, height, contentWidth});
	}

	if (screen === 'scan') {
		return h(LogScreen, {title: 'Scan laeuft', logs, offset: logOffset, visibleRows: logVisibleRows, width, height, contentWidth, footer: 'Up/Down scroll | End follows tail | Parallel scan + Modrinth batch lookup'});
	}

	if (screen === 'decision') {
		return h(DecisionScreen, {queue: manualQueue, index: manualIndex, width, height, contentWidth});
	}

	if (screen === 'build') {
		return h(LogScreen, {title: 'Serverpack wird gebaut', logs, offset: logOffset, visibleRows: logVisibleRows, width, height, contentWidth, footer: 'Up/Down scroll | End follows tail | Kopiere Mods, configs und Report'});
	}

	return h(ReportScreen, {candidates, outputPath, offset: reportOffset, visibleRows: reportVisibleRows, width, height, contentWidth});
}

function handleSetupInput({input, key, defaults, focus, setFocus, profileIndex, setProfileIndex, profileOffset, setProfileOffset, profileVisibleRows, setModsPath, setOutputPath, startScan}) {
	const profileCount = defaults?.profiles?.length ?? 0;

	if (key.tab) {
		setFocus((focus + 1) % 4);
		return;
	}

	if (input === 's') {
		startScan();
		return;
	}

	if (focus === 2) {
		if (key.upArrow) {
			const nextIndex = Math.max(0, profileIndex - 1);
			setProfileIndex(nextIndex);
			setProfileOffset(scrollIntoView(nextIndex, profileOffset, profileVisibleRows));
		} else if (key.downArrow) {
			const nextIndex = Math.min(profileCount - 1, profileIndex + 1);
			setProfileIndex(nextIndex);
			setProfileOffset(scrollIntoView(nextIndex, profileOffset, profileVisibleRows));
		} else if (key.pageUp) {
			const nextIndex = Math.max(0, profileIndex - profileVisibleRows);
			setProfileIndex(nextIndex);
			setProfileOffset(scrollIntoView(nextIndex, profileOffset, profileVisibleRows));
		} else if (key.pageDown) {
			const nextIndex = Math.min(profileCount - 1, profileIndex + profileVisibleRows);
			setProfileIndex(nextIndex);
			setProfileOffset(scrollIntoView(nextIndex, profileOffset, profileVisibleRows));
		} else if (key.home) {
			setProfileIndex(0);
			setProfileOffset(0);
		} else if (key.end) {
			const nextIndex = Math.max(0, profileCount - 1);
			setProfileIndex(nextIndex);
			setProfileOffset(Math.max(0, profileCount - profileVisibleRows));
		} else if (key.return && profileCount > 0) {
			setModsPath(defaults.profiles[profileIndex]);
			setFocus(0);
		}
		return;
	}

	if (focus === 3 && key.return) {
		startScan();
		return;
	}

	if (focus !== 0 && focus !== 1) {
		return;
	}

	const update = focus === 0 ? setModsPath : setOutputPath;
	if (key.backspace || key.delete) {
		update(previous => previous.slice(0, -1));
	} else if (input && !key.ctrl && !key.meta && input.length === 1) {
		update(previous => previous + input);
	}
}

function handleLogInput({key, logs, logOffset, logVisibleRows, setLogOffset, setLogFollowTail}) {
	const maxOffset = Math.max(0, logs.length - logVisibleRows);
	if (key.upArrow) {
		setLogFollowTail(false);
		setLogOffset(Math.max(0, logOffset - 1));
	} else if (key.downArrow) {
		const nextOffset = Math.min(maxOffset, logOffset + 1);
		setLogOffset(nextOffset);
		setLogFollowTail(nextOffset === maxOffset);
	} else if (key.pageUp) {
		setLogFollowTail(false);
		setLogOffset(Math.max(0, logOffset - logVisibleRows));
	} else if (key.pageDown) {
		const nextOffset = Math.min(maxOffset, logOffset + logVisibleRows);
		setLogOffset(nextOffset);
		setLogFollowTail(nextOffset === maxOffset);
	} else if (key.home) {
		setLogFollowTail(false);
		setLogOffset(0);
	} else if (key.end) {
		setLogFollowTail(true);
		setLogOffset(maxOffset);
	}
}

function handleReportInput({input, key, candidates, reportOffset, reportVisibleRows, setReportOffset, resetToSetup}) {
	const maxOffset = Math.max(0, candidates.length - reportVisibleRows);
	if (input === 'b') {
		resetToSetup();
	} else if (key.upArrow) {
		setReportOffset(Math.max(0, reportOffset - 1));
	} else if (key.downArrow) {
		setReportOffset(Math.min(maxOffset, reportOffset + 1));
	} else if (key.pageUp) {
		setReportOffset(Math.max(0, reportOffset - reportVisibleRows));
	} else if (key.pageDown) {
		setReportOffset(Math.min(maxOffset, reportOffset + reportVisibleRows));
	} else if (key.home) {
		setReportOffset(0);
	} else if (key.end) {
		setReportOffset(maxOffset);
	}
}

function handleDecisionInput({input, manualQueue, manualIndex, setManualIndex, setCandidates, setScreen}) {
	const current = manualQueue[manualIndex];
	if (!current) {
		setScreen('build');
		return;
	}

	if (input === 'o') {
		openExternal(current.page_url);
		return;
	}

	if (!['s', 'c', 'k'].includes(input)) {
		return;
	}

	const decision = input === 's' ? 'server' : input === 'c' ? 'client' : 'skip';
	setCandidates(previous => previous.map(candidate => {
		if (candidate.sha1 !== current.sha1) {
			return candidate;
		}
		return {...candidate, decision, reason: `Manuell in React TUI als ${decision} markiert.`};
	}));

	if (manualIndex >= manualQueue.length - 1) {
		setScreen('build');
	} else {
		setManualIndex(manualIndex + 1);
	}
}

function needsManualDecision(candidate) {
	return candidate.decision === 'unknown' || candidate.source === 'curseforge' || candidate.source === 'unknown';
}

function Frame({children, width, height}) {
	const frameWidth = Math.max(1, width - 1);
	const frameHeight = Math.max(1, height - 1);
	return h(Box, {flexDirection: 'column', width: frameWidth, height},
		h(Box, {borderStyle: 'round', borderColor: palette.panel, paddingX: 1, flexDirection: 'column', width: frameWidth, height: frameHeight},
			h(Text, {bold: true, color: palette.gold}, 'Keksgames Server Modpack Creator'),
			h(Box, {flexDirection: 'column'}, children)
		),
		h(Text, {color: palette.muted}, 'Tab wechseln | q beenden | Ctrl+C kill')
	);
}

function SetupScreen({defaults, modsPath, outputPath, focus, profileIndex, profileOffset, profileVisibleRows, width, height, contentWidth}) {
	const profiles = defaults?.profiles ?? [];
	const visibleProfiles = profiles.slice(profileOffset, profileOffset + profileVisibleRows);
	return h(Frame, {width, height},
		h(Text, {color: palette.muted}, 'React/Ink TUI - Minecraft Serverpack aus Launcher-Mods bauen'),
		h(Field, {label: 'Mods', value: modsPath, active: focus === 0, width: contentWidth}),
		h(Field, {label: 'Output', value: outputPath, active: focus === 1, width: contentWidth}),
		h(Box, {marginTop: 1, flexDirection: 'column'},
			h(Text, {color: focus === 2 ? palette.accent : palette.gold}, 'Gefundene Profile'),
			profiles.length === 0
				? h(Text, {color: palette.muted}, 'Keine Profile gefunden. Pfad oben eintippen.')
				: visibleProfiles.map((profile, localIndex) => {
					const absoluteIndex = profileOffset + localIndex;
					return h(Text, {key: profile, color: focus === 2 && absoluteIndex === profileIndex ? palette.good : palette.muted},
						clip(`${focus === 2 && absoluteIndex === profileIndex ? '>' : ' '} ${profileName(profile).padEnd(28)} ${clip(profile, Math.max(16, contentWidth - 32))}`, contentWidth)
					)
				})
		),
		profiles.length > profileVisibleRows ? h(Text, {color: palette.muted}, `Profile ${profileOffset + 1}-${Math.min(profileOffset + profileVisibleRows, profiles.length)} von ${profiles.length} | Up/Down/Page scroll`) : null,
		h(Box, {marginTop: 1},
			h(Text, {color: focus === 3 ? palette.good : palette.muted}, '[Enter] Start  '),
			h(Text, {color: palette.muted}, 'oder Taste s')
		)
	);
}

function Field({label, value, active, width}) {
	const prefix = `${active ? '>' : ' '} ${label}: `;
	return h(Box, {marginTop: 1, flexDirection: 'column'},
		h(Text, {color: active ? palette.accent : palette.gold}, `${prefix}${clip(value || ' ', Math.max(1, width - prefix.length))}`)
	);
}

function LogScreen({title, logs, offset, visibleRows, width, height, contentWidth, footer}) {
	const visibleLogs = logs.length ? logs.slice(offset, offset + visibleRows) : ['Warte auf Backend...'];
	return h(Frame, {width, height},
		h(Text, {color: palette.accent}, title),
		h(Box, {marginTop: 1, flexDirection: 'column'},
			visibleLogs.map((line, index) =>
				h(Text, {key: `${offset + index}-${line}`, color: offset + index === logs.length - 1 ? palette.good : undefined}, clip(line, contentWidth))
			)
		),
		logs.length > visibleRows ? h(Text, {color: palette.muted}, `Log ${offset + 1}-${Math.min(offset + visibleRows, logs.length)} von ${logs.length}`) : null,
		h(Text, {color: palette.muted}, footer)
	);
}

function DecisionScreen({queue, index, width, height, contentWidth}) {
	const current = queue[index];
	if (!current) {
		return h(LogScreen, {title: 'Keine manuellen Entscheidungen mehr', logs: ['Starte Build...'], offset: 0, visibleRows: Math.max(5, height - 8), width, height, contentWidth, footer: ''});
	}

	return h(Frame, {width, height},
		h(Text, {color: palette.warn}, `Manuelle Entscheidung ${index + 1}/${queue.length}`),
		h(Text, {bold: true, color: palette.gold}, clip(current.name, contentWidth)),
		h(Text, null, clip(`Datei: ${current.file}`, contentWidth)),
		h(Text, null, clip(`Version: ${current.version}`, contentWidth)),
		h(Text, null, clip(`Quelle: ${current.source}`, contentWidth)),
		h(Text, {color: palette.muted}, clip(current.reason || 'Bitte pruefen.', contentWidth)),
		h(Text, {color: palette.accent}, clip(current.page_url || 'Kein Link gefunden', contentWidth)),
		h(Box, {marginTop: 1},
			h(Text, {color: palette.good}, 's Server  '),
			h(Text, {color: palette.warn}, 'c Client  '),
			h(Text, {color: palette.muted}, 'k Skip  '),
			h(Text, {color: palette.accent}, 'o Link')
		)
	);
}

function ReportScreen({candidates, outputPath, offset, visibleRows, width, height, contentWidth}) {
	const included = candidates.filter(candidate => candidate.decision === 'server').length;
	const excluded = candidates.length - included;
	const rows = candidates.slice(offset, offset + visibleRows);

	return h(Frame, {width, height},
		h(Text, {color: palette.good}, `Fertig: ${included} Server-Mods, ${excluded} ausgeschlossen`),
		h(Text, {color: palette.muted}, clip(outputPath, contentWidth)),
		h(Box, {marginTop: 1, flexDirection: 'column'},
			rows.map(candidate =>
				h(Text, {key: candidate.sha1, color: candidate.decision === 'server' ? palette.good : palette.muted},
					clip(`${candidate.decision.padEnd(7)} ${candidate.source.padEnd(10)} ${candidate.name}`, contentWidth)
				)
			)
		),
		candidates.length > visibleRows ? h(Text, {color: palette.muted}, `Mods ${offset + 1}-${Math.min(offset + visibleRows, candidates.length)} von ${candidates.length} | Up/Down/Page scroll`) : null,
		h(Text, {color: palette.accent}, 'o Ausgabeordner oeffnen | b Zurueck zum Start')
	);
}

function profileName(path) {
	const parts = path.split(/[\\/]/).filter(Boolean);
	return parts.at(-2) ?? parts.at(-1) ?? path;
}

function clip(value, maxLength) {
	if (value.length <= maxLength) {
		return value;
	}

	return `...${value.slice(-(maxLength - 3))}`;
}

function scrollIntoView(index, offset, visibleRows) {
	if (index < offset) {
		return index;
	}

	if (index >= offset + visibleRows) {
		return index - visibleRows + 1;
	}

	return offset;
}

render(h(App), {alternateScreen: isInteractive, interactive: isInteractive});
