import type { DefinitionHistoryEntry } from '../types';

// Columns that change as a side effect of other edits (or never), so listing them is noise.
const DERIVED_FIELDS = new Set(['id', 'indicator_id', 'is_calculated']);
const MAX_VALUE_LENGTH = 40;

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

// null, undefined and '' all mean "not set" (a form save turns null into '').
const normalized = (value: unknown) => JSON.stringify(value === undefined || value === '' ? null : value);

function show(value: unknown): string {
  if (value === null || value === undefined || value === '') return '(empty)';
  return typeof value === 'string' ? value : JSON.stringify(value);
}

/** What a KPI definition history entry did, in words: "changed unit of measure (h -> kWh)". */
export function describeDefinitionChange(entry: DefinitionHistoryEntry): string {
  switch (entry.change_type) {
    case 'CREATE':
      return 'created the KPI';
    case 'SOFT_DELETE':
      return 'deleted the KPI';
    case 'HARD_DELETE':
      return 'permanently deleted the KPI';
    case 'UPDATE': {
      const before = asRecord(entry.old_value);
      const after = asRecord(entry.new_value);
      const changes = Object.keys(after)
        .filter((key) => !DERIVED_FIELDS.has(key) && normalized(before[key]) !== normalized(after[key]))
        .map((key) => {
          const label = key.replace(/_/g, ' ');
          const from = show(before[key]);
          const to = show(after[key]);
          return from.length + to.length <= MAX_VALUE_LENGTH ? `${label} (${from} -> ${to})` : label;
        });
      return changes.length ? `changed ${changes.join(', ')}` : 'saved without changes';
    }
    default:
      return entry.change_type.toLowerCase();
  }
}
