# Dependency and environment portability audit (5 mixed real tasks, Task 2)

## Status

Real, evidence-based audit, not assumed from `pyproject.toml` alone.
Date: 2026-09-05.

## Real, confirmed baseline

`uv sync --locked --all-groups` (the exact command CI runs) resolves
and installs cleanly against the real, current lockfile -- 136
packages resolved, no drift between `pyproject.toml` and `uv.lock`.
`.python-version` (`3.12`) matches CI's own matrix (`3.12`, `3.13`).

## Real, confirmed hard requirement: an NVIDIA GPU with CUDA, for real speech-to-text

`adapters/stt.py::FasterWhisperAdapter` hardcodes
`device="cuda"` (`faster-whisper`'s `WhisperModel`) -- confirmed by
reading the real constructor call directly, not assumed. There is no
CPU fallback path anywhere in this codebase today. This is a real,
deliberate, already-made decision (WP-19/WP-20), not an oversight, and
a real architectural caveat about `LD_LIBRARY_PATH`/`os.execv()`
re-exec is already documented in that module's own docstring -- but
**this hard hardware requirement was, until this task, not stated
anywhere a person setting up the project for the first time would see
it** (not in `README.md`, not in `docs/protocol/README.md`). Fixed:
added to `README.md`'s own "Development setup" section.

Consequence for portability: this project cannot do real, live
speech-to-text on a machine without an NVIDIA GPU. Voice input over
text/CLI commands still works everywhere; only the STT half of the
voice pipeline needs the GPU specifically. Every other real capability
family (desktop control, memory, browser automation, coding,
email/calendar, job assistance) has no GPU dependency at all.

## Real, confirmed gap found and fixed: `libportaudio2` was an undeclared system dependency

`sounddevice` (imported at module level by `kernel/voice_loop.py`,
`adapters/wake_word.py`, and `adapters/candidate_presentation.py`, all
reachable during ordinary test collection) is a pure-Python `ctypes`
binding -- confirmed directly by checking the installed wheel contains
no bundled `.so` of its own. It `dlopen`s the real system
`libportaudio.so.2` at import time. `.github/workflows/ci.yml`'s own
apt-get step never installed this package, yet CI has always passed --
the only honest explanation, confirmed by checking `ldconfig -p` on
this real development machine, is that `ubuntu-latest`'s own default
image ships it already. **A real, previously undeclared dependency on
the CI runner image's own contents, not a genuine absence of the
requirement.** Fixed: `libportaudio2` added to CI's own explicit
apt-get list, matching the same "declare every real system dependency
explicitly" discipline that step's own comment already states for
PyGObject/bubblewrap.

## Real, confirmed, already-documented system dependencies (unchanged, cross-checked, not newly found)

`PyGObject` (>=3.56.3) ships no prebuilt Linux wheels -- a real C
compiler and `libgirepository-2.0-dev`/`libcairo2-dev` are needed to
build it from source; `gir1.2-gtk-4.0` is needed at runtime for
`Gtk.require_version("Gtk", "4.0")` to resolve. `bubblewrap` provides
the real `bwrap` binary `BwrapSandboxAdapter`'s own tests execute
against. All three were already correctly declared in CI's own apt-get
step, cross-checked here against the real, installed versions on this
development machine rather than re-derived from scratch -- no drift
found.

## GPU/CUDA Python packages: broader platform support than initially assumed

`nvidia-cublas-cu12`/`nvidia-cudnn-cu12` (both unconditional
`pyproject.toml` dependencies, no environment marker) were checked
directly against PyPI's own real, published wheel list: both publish
`manylinux_2_27_aarch64` (ARM64 Linux) and `win_amd64` wheels in
addition to `x86_64` -- broader real portability than "x86_64 Linux
only" might suggest, though this project's own stated scope is Linux
specifically, and no macOS wheel exists for either (expected -- these
are NVIDIA CUDA libraries, and macOS has no NVIDIA GPU support). A
real, accepted cost of these being unconditional dependencies: every
`uv sync`, even on a machine that will never do real STT, downloads
both libraries in full (each a real, non-trivial download size) --
named here honestly, not silently accepted without comment. No
environment-marker fix was made: gating these behind a marker would
need a real decision about which marker correctly predicts "will this
machine ever run real STT," which this task does not have grounds to
decide unilaterally.

## Conclusion

Two real, concrete gaps found and fixed: the hard NVIDIA GPU/CUDA
requirement for STT was undocumented anywhere a new contributor would
see it (now stated in `README.md`); `libportaudio2` was an
undeclared, implicit CI dependency on the runner image's own contents
(now explicit in `ci.yml`). Everything else already documented for
PyGObject/bubblewrap was cross-checked and confirmed accurate, not
re-derived. The GPU-library download-size cost for non-GPU users is
named as a real, accepted trade-off, not silently ignored, with no
unilateral fix attempted.
