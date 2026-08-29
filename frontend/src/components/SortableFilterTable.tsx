import { useMemo, useState, ReactNode } from "react";

export interface ColumnDef<T> {
  key: string;
  label: string;
  filterType?: "text" | "select";
  // For columns with a custom cell display (buttons, dropdowns, badges).
  render?: (row: T) => ReactNode;
  // How to read this column's value for sorting/filtering. Defaults to
  // row[key] - only needed when render() shows something different from
  // the raw underlying value (e.g. a formatted date or a dropdown).
  getValue?: (row: T) => string | number | null;
}

interface Props<T> {
  columns: ColumnDef<T>[];
  rows: T[];
  rowKey: (row: T) => string | number;
}

export default function SortableFilterTable<T extends Record<string, any>>({
  columns,
  rows,
  rowKey,
}: Props<T>) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [filters, setFilters] = useState<Record<string, string>>({});

  function getCellValue(row: T, col: ColumnDef<T>): string | number | null {
    if (col.getValue) return col.getValue(row);
    const v = row[col.key];
    return v === undefined ? null : v;
  }

  function toggleSort(key: string) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  }

  const filteredSorted = useMemo(() => {
    let result = rows.filter((row) =>
      columns.every((col) => {
        const filterVal = filters[col.key];
        if (!filterVal) return true;
        const cellVal = getCellValue(row, col);
        if (col.filterType === "select") {
          return String(cellVal ?? "") === filterVal;
        }
        return String(cellVal ?? "").toLowerCase().includes(filterVal.toLowerCase());
      })
    );

    if (sortKey) {
      const col = columns.find((c) => c.key === sortKey);
      result = [...result].sort((a, b) => {
        const av = col ? getCellValue(a, col) : null;
        const bv = col ? getCellValue(b, col) : null;
        if (av == null && bv == null) return 0;
        if (av == null) return sortDir === "asc" ? -1 : 1;
        if (bv == null) return sortDir === "asc" ? 1 : -1;
        if (typeof av === "number" && typeof bv === "number") {
          return sortDir === "asc" ? av - bv : bv - av;
        }
        return sortDir === "asc"
          ? String(av).localeCompare(String(bv))
          : String(bv).localeCompare(String(av));
      });
    }

    return result;
  }, [rows, filters, sortKey, sortDir, columns]);

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="bg-gray-100">
          <tr>
            {columns.map((col) => {
              const uniqueValues =
                col.filterType === "select"
                  ? Array.from(
                      new Set(rows.map((r) => String(getCellValue(r, col) ?? "")))
                    )
                      .filter(Boolean)
                      .sort()
                  : [];
              return (
                <th key={col.key} className="p-2 align-top">
                  <button
                    onClick={() => toggleSort(col.key)}
                    className="font-semibold flex items-center gap-1 hover:text-blue-600 whitespace-nowrap"
                  >
                    {col.label}
                    <span className="text-gray-400">
                      {sortKey === col.key ? (sortDir === "asc" ? "▲" : "▼") : "⇅"}
                    </span>
                  </button>
                  {col.filterType === "text" && (
                    <input
                      type="text"
                      placeholder="Filter..."
                      value={filters[col.key] || ""}
                      onChange={(e) =>
                        setFilters((f) => ({ ...f, [col.key]: e.target.value }))
                      }
                      className="mt-1 w-full border rounded px-1 py-0.5 text-xs font-normal"
                    />
                  )}
                  {col.filterType === "select" && (
                    <select
                      value={filters[col.key] || ""}
                      onChange={(e) =>
                        setFilters((f) => ({ ...f, [col.key]: e.target.value }))
                      }
                      className="mt-1 w-full border rounded px-1 py-0.5 text-xs font-normal"
                    >
                      <option value="">All</option>
                      {uniqueValues.map((v) => (
                        <option key={v} value={v}>
                          {v}
                        </option>
                      ))}
                    </select>
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {filteredSorted.map((row) => (
            <tr key={rowKey(row)} className="border-t">
              {columns.map((col) => (
                <td key={col.key} className="p-2 align-top">
                  {col.render ? col.render(row) : String(getCellValue(row, col) ?? "—")}
                </td>
              ))}
            </tr>
          ))}
          {filteredSorted.length === 0 && (
            <tr>
              <td colSpan={columns.length} className="p-4 text-center text-gray-400">
                No matching rows.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
