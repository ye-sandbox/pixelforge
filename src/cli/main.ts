#!/usr/bin/env node
import { pathToFileURL } from 'node:url';
import { parseArgs } from 'node:util';

export type CliCommand = 'init' | 'render' | 'check' | 'diff';

export interface ParsedCli {
  readonly command: CliCommand | undefined;
  readonly help: boolean;
  readonly version: boolean;
  readonly positionals: readonly string[];
}

const VALID_COMMANDS = new Set<string>(['init', 'render', 'check', 'diff']);

export const CLI_VERSION = '0.1.0';

export function formatHelp(): string {
  return [
    'pixelforge — Code-drawn indexed pixel art engine & visual critic CLI',
    '',
    'Usage:',
    '  pixelforge <command> [options]',
    '',
    'Commands:',
    '  init     Scaffold a new style pack or asset module',
    '  render   Render asset module(s) to PNG, spritesheet, manifest, and contact sheet',
    '  check    Run static and runtime guard checks',
    '  diff     Compare rendered output against a baseline',
    '',
    'Options:',
    '  -h, --help     Show help',
    '  -v, --version  Show version',
  ].join('\n');
}

export function parseCliArgs(argv: readonly string[]): ParsedCli {
  const { values, positionals } = parseArgs({
    args: [...argv],
    allowPositionals: true,
    strict: false,
    options: {
      help: { type: 'boolean', short: 'h', default: false },
      version: { type: 'boolean', short: 'v', default: false },
    },
  });

  const [first, ...rest] = positionals;
  const command =
    first !== undefined && VALID_COMMANDS.has(first) ? (first as CliCommand) : undefined;

  return {
    command,
    help: Boolean(values.help),
    version: Boolean(values.version),
    positionals: command !== undefined ? rest : positionals,
  };
}

export function runCli(argv: readonly string[]): number {
  const parsed = parseCliArgs(argv);

  if (parsed.version) {
    process.stdout.write(`${CLI_VERSION}\n`);
    return 0;
  }

  if (parsed.help || parsed.command === undefined) {
    process.stdout.write(`${formatHelp()}\n`);
    return parsed.help || parsed.positionals.length === 0 ? 0 : 1;
  }

  process.stderr.write(`Command "${parsed.command}" is not yet implemented.\n`);
  return 1;
}

const entryHref = process.argv[1] ? pathToFileURL(process.argv[1]).href : '';
if (import.meta.url === entryHref) {
  process.exitCode = runCli(process.argv.slice(2));
}
