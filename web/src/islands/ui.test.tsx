/** The header tooltips are the site's glossary — check they actually attach. */

import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { GLOSSARY } from '../lib/glossary';
import { Th } from './ui';

describe('Th', () => {
  it('explains an abbreviation in a styled panel, not a native title', () => {
    const markup = renderToStaticMarkup(<Th metric="fd100" label="FD/100" />);
    expect(markup).toContain('Fouls drawn per 100 possessions');
    expect(markup).toContain('role="tooltip"');
    expect(markup).toContain('has-help');
    expect(markup).not.toContain('title='); // the OS tooltip would not match the site
  });

  it('ties the panel to its header for screen readers, and is focusable', () => {
    const markup = renderToStaticMarkup(<Th metric="pir" label="PIR" />);
    expect(markup).toContain('aria-describedby="help-pir"');
    expect(markup).toContain('id="help-pir"');
    expect(markup).toContain('tabindex="0"');
  });

  it('hangs the panel from the right edge for trailing columns', () => {
    expect(renderToStaticMarkup(<Th metric="pm" label="+/-" alignEnd />)).toContain('tip tip-end');
    expect(renderToStaticMarkup(<Th metric="pm" label="+/-" />)).toContain('class="tip"');
  });

  it('leaves plain headers alone', () => {
    const markup = renderToStaticMarkup(<Th label="#" />);
    expect(markup).not.toContain('has-help');
    expect(markup).not.toContain('role="tooltip"');
  });

  it('carries sort state for assistive tech', () => {
    const markup = renderToStaticMarkup(
      <Th metric="pir_avg" label="PIR/g" sortable sorted="descending" />,
    );
    expect(markup).toContain('aria-sort="descending"');
    expect(markup).toContain('sortable');
  });

  it('has a description for every metric, none of them empty', () => {
    for (const [key, text] of Object.entries(GLOSSARY)) {
      expect(text.length, `${key} needs a real description`).toBeGreaterThan(10);
    }
  });
});
