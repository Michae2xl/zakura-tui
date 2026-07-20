# Installer PATH Guidance Design

## Problem

The local installer creates `zakura-status` and `zakura-start` links in
`$HOME/.local/bin`, but that directory is not present in every user's `PATH`.
The installer currently reports success without warning about this condition.
The README suggests an `export PATH=...` command, but does not explain that the
change only lasts for the current shell session.

As a result, installation can succeed while both commands still fail with
`command not found`.

## Goals

- Detect when the selected local binary directory is absent from `PATH`.
- Keep installation non-interactive and successful.
- Print immediately usable and persistent remediation instructions.
- Avoid changing user shell configuration without explicit consent.
- Document the distinction between temporary and persistent `PATH` changes.
- Cover the behavior with an automated regression test.

## Non-goals

- Detect or rewrite every supported shell configuration file.
- Install into privileged directories such as `/usr/local/bin`.
- Change the package entry points or runtime behavior of either TUI command.
- Add a dependency for shell or environment detection.

## Installer behavior

After creating both command links, the installer will compare `bin_dir` with
the current `PATH` using delimiter-aware matching. This prevents partial path
matches such as `/home/user/.local/bin-old` from being accepted.

When `bin_dir` is already present, the existing success and configuration
messages remain concise and no warning is printed.

When `bin_dir` is absent, installation still succeeds and the installer prints:

1. A warning that the commands are installed but not currently discoverable.
2. An `export PATH="$HOME/.local/bin:$PATH"` command for the current session.
3. A shell-neutral recommendation to add the same export to the user's shell
   startup file for future sessions.

The installer will not append to `.profile`, `.bashrc`, `.zshrc`, or any other
startup file.

## Documentation

The README installation section will:

- Run the installer first.
- Explain that the installer warns when `~/.local/bin` is missing from `PATH`.
- Show the temporary export command separately.
- Show a Bash-compatible persistent example using `~/.profile`.
- Tell users of other shells to place the export in the appropriate startup
  file.

## Testing

An integration-style installer test will run a copied installer from a
temporary repository layout with:

- A temporary `HOME`.
- A controlled `PATH` that excludes `$HOME/.local/bin`.
- A lightweight fake `python3` that creates the expected virtual-environment
  command targets without installing the package.

The test will assert that installation succeeds, both links are created, and
the output contains the missing-`PATH` warning plus temporary and persistent
guidance.

A second invocation with `$HOME/.local/bin` included in `PATH` will assert that
the warning is absent. Existing package and TUI tests must continue to pass.

## Acceptance criteria

- A user whose `PATH` omits `~/.local/bin` receives actionable guidance during
  installation.
- A user whose `PATH` already includes the directory receives no unnecessary
  warning.
- The installer never edits shell startup files.
- The README no longer presents a session-only export as if it completed the
  installation permanently.
- The full test suite passes.
