export function metresPerUnit(units) {
  return { m: 1, cm: 0.01, mm: 0.001 }[units] ?? null;
}
export function midpoint(a, b) {
  validate(a, b);
  return a.map((value, i) => (value + b[i]) / 2);
}
export function distanceMetres(a, b, units = 'm') {
  validate(a, b);
  const factor = metresPerUnit(units);
  if (!factor) throw new Error('Chưa xác định đơn vị.');
  return Math.hypot(...a.map((value, i) => value - b[i])) * factor;
}
function validate(a, b) {
  if (!Array.isArray(a) || !Array.isArray(b) || a.length !== 3 || b.length !== 3 || ![...a, ...b].every(Number.isFinite)) throw new Error('Cần hai điểm 3D hợp lệ.');
}