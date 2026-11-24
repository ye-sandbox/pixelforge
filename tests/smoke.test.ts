import { describe, expect, it } from 'vitest';
import { parseCliArgs, runCli } from '../src/cli/main.js';
import { TRANSPARENT_INDEX } from '../src/index.js';

describe('pixelforge bootstrap smoke tests', () => {
  it('reserves index 255 as TRANSPARENT_INDEX', () => {
    expect(TRANSPARENT_INDEX).toBe(255);
  });

  it('parses CLI help and subcommands', () => {
    const helpArgs = parseCliArgs(['--help']);
    expect(helpArgs.help).toBe(true);
    expect(helpArgs.command).toBeUndefined();

    const renderArgs = parseCliArgs(['render', 'assets/laptop.asset.ts']);
    expect(renderArgs.command).toBe('render');
    expect(renderArgs.positionals).toEqual(['assets/laptop.asset.ts']);
  });

  it('returns exit code 0 for --help', () => {
    expect(runCli(['--help'])).toBe(0);
  });
});
