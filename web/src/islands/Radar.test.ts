import { describe, expect, it } from 'vitest';
import { spokePoint } from './Radar';

// Derived, not hardcoded: the plot can be resized without rewriting the tests.
const CENTRE = spokePoint(0, 0, 4);
const CX = CENTRE.x;
const CY = CENTRE.y;
const R = CY - spokePoint(100, 0, 4).y;

describe('spokePoint', () => {
  it('puts the first spoke straight up', () => {
    const p = spokePoint(100, 0, 5);
    expect(p.x).toBeCloseTo(CX, 5);
    expect(p.y).toBeCloseTo(CY - R, 5);
  });

  it('places a zero percentile at the centre', () => {
    const p = spokePoint(0, 2, 5);
    expect(p.x).toBeCloseTo(CX, 5);
    expect(p.y).toBeCloseTo(CY, 5);
  });

  it('scales the radius with the percentile', () => {
    expect(CY - spokePoint(50, 0, 4).y).toBeCloseTo(R / 2, 5);
  });

  it('spaces spokes evenly around the circle', () => {
    const [up, right, down, left] = [0, 1, 2, 3].map((i) => spokePoint(100, i, 4));
    expect(up!.y).toBeCloseTo(CY - R, 5);
    expect(right!.x).toBeCloseTo(CX + R, 5);
    expect(down!.y).toBeCloseTo(CY + R, 5);
    expect(left!.x).toBeCloseTo(CX - R, 5);
  });

  it('clamps out-of-range percentiles instead of drawing outside the plot', () => {
    expect(CY - spokePoint(140, 0, 5).y).toBeCloseTo(R, 5);
    expect(CY - spokePoint(-20, 0, 5).y).toBeCloseTo(0, 5);
  });
});
