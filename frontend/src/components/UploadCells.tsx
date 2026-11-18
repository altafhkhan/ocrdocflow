// The "File" and "Uploaded" cells shared by the upload tables on the
// dashboard and the free-trial page. Sized so the table stays readable
// on a phone held upright.

/**
 * File name. The column has a fixed width, so a long name wraps onto more
 * lines instead of being cut off or pushing the other columns off screen;
 * hovering shows the whole name too. There is no Status column: a finished
 * upload needs no label, so only an upload that failed or is still being
 * read gets a small tag under its name.
 */
export function FileNameCell({ name, status }: { name: string; status: string }) {
  return (
    <td className="p-3 align-top" title={name}>
      <span className="block [overflow-wrap:anywhere]">{name}</span>
      {status === "failed" && (
        <span className="mt-1 inline-block px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800">
          could not be read
        </span>
      )}
      {status !== "failed" && status !== "done" && (
        <span className="mt-1 inline-block px-2 py-0.5 rounded text-xs font-medium bg-yellow-100 text-yellow-800">
          {status}
        </span>
      )}
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
