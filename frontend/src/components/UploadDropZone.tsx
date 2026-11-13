import { useRef, useState } from "react";

const ACCEPTED_EXTENSIONS = [".pdf", ".jpg", ".jpeg", ".png"];

interface Props {
  /** The page keeps this ref so it can clear the input after an upload. */
  inputRef: React.RefObject<HTMLInputElement>;
  /** No picking and no dropping while true (upload running, email needed, ...). */
  disabled: boolean;
  /** Shows "Working on it..." instead of the idle text. */
  busy: boolean;
  idleText: string;
  /** Called with one accepted file, whether it was picked or dropped. */
  onFile: (file: File) => void;
  /** Called with a plain-English reason when a dropped file is not accepted. */
  onReject: (message: string) => void;
}

/**
 * The dashed upload box: click to choose a file, or drag a file onto it.
 *
 * The file dialog filters by type through `accept`; a dropped file skips
 * that filter, so the same check is repeated here. Only the first file of
 * a multi-file drop is taken - the app processes one document at a time.
 */
export default function UploadDropZone({ inputRef, disabled, busy, idleText, onFile, onReject }: Props) {
  const [dragging, setDragging] = useState(false);
  // dragenter/dragleave also fire for child elements; counting them keeps
  // the highlight steady while the pointer moves across the box.
  const depth = useRef(0);

  function hasFiles(e: React.DragEvent) {
    return Array.from(e.dataTransfer?.types ?? []).includes("Files");
  }

  function onDragEnter(e: React.DragEvent) {
    if (!hasFiles(e)) return;
    e.preventDefault();
    depth.current += 1;
    if (!disabled) setDragging(true);
  }

  function onDragOver(e: React.DragEvent) {
    if (!hasFiles(e)) return;
    // Without this the browser opens the dropped file instead of handing it to us.
    e.preventDefault();
    e.dataTransfer.dropEffect = disabled ? "none" : "copy";
  }

  function onDragLeave(e: React.DragEvent) {
    if (!hasFiles(e)) return;
    depth.current = Math.max(0, depth.current - 1);
    if (depth.current === 0) setDragging(false);
  }

  function onDrop(e: React.DragEvent) {
    if (!hasFiles(e)) return;
    e.preventDefault();
    depth.current = 0;
    setDragging(false);
    if (disabled) return;

    const files = Array.from(e.dataTransfer.files);
    if (files.length === 0) return;
    const file = files[0];
    const name = file.name.toLowerCase();
    if (!ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext))) {
      onReject(`"${file.name}" is not a PDF, JPG or PNG file.`);
      return;
    }
    onFile(file);
  }

  const look = disabled
    ? "border-gray-200 text-gray-400"
    : dragging
      ? "border-blue-500 bg-blue-50 text-blue-700"
      : "border-gray-300 cursor-pointer hover:border-blue-400 text-gray-600";

  return (
    <label
      onDragEnter={onDragEnter}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      className={`block border-2 border-dashed rounded-lg p-6 text-center transition-colors ${look}`}
    >
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED_EXTENSIONS.join(",")}
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onFile(file);
        }}
        disabled={disabled}
      />
      {busy ? "Working on it..." : dragging ? "Drop the file to upload it" : idleText}
    </label>
  );
}
