// The "File" and "Uploaded" cells shared by the upload tables on the
// dashboard and the free-trial page. Sized so the table stays readable
// on a phone held upright.

/**
 * File name. The column has a fixed width, so a long name wraps onto more
 * lines instead of being cut off or pushing the other columns off screen;
 * hovering shows the whole name too. There is no Status column (it does
 * not fit a phone screen); the status is a small tag under the name:
 * "done" once the file has been read, "saved" once the user has pressed
 * Save in Review & Save ("partly saved" for a file with several invoices
 * when only some are saved), or "could not be read".
 */
export function FileNameCell({
  name,
  status,
  reviewStatus,
}: {
  name: string;
  status: string;
  reviewStatus?: string | null;
}) {
  const label = status === "failed" ? "could not be read" : status === "done" ? reviewStatus || "done" : status;
  const colour =
    status === "failed"
      ? "bg-red-100 text-red-800"
      : status !== "done"
        ? "bg-yellow-100 text-yellow-800"
        : reviewStatus === "saved"
          ? "bg-blue-100 text-blue-800"
          : reviewStatus
            ? "bg-amber-100 text-amber-800"
            : "bg-green-100 text-green-800";
  return (
    <td className="p-3 align-top" title={name}>
      <span className="block [overflow-wrap:anywhere]">{name}</span>
      <span className={`mt-1 inline-block px-2 py-0.5 rounded text-xs font-medium ${colour}`}>{label}</span>
    </td>
  );
}

/** Upload time: the date on one line, the time on the line below. */
export function UploadedCell({ at }: { at: string }) {
  const when = new Date(at);
  return (
    <td className="py-3 px-2 align-top whitespace-nowrap">
      <span className="block">{when.toLocaleDateString()}</span>
      <span className="block text-gray-500">
        {when.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}
      </span>
    </td>
  );
}

/** Column widths for those tables (use with `table-fixed`). */
export function UploadColumns() {
  return (
    <colgroup>
      <col />
      <col className="w-24" />
      <col className="w-24" />
    </colgroup>
  );
}
