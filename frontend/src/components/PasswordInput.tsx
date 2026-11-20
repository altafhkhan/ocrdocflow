import { InputHTMLAttributes, useState } from "react";

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & {
  /** Classes for the box around the field (spacing lives here, not on the input). */
  wrapperClassName?: string;
};

/**
 * A password field with a show/hide button (the eye), so people can check
 * what they typed - on a phone keyboard especially.
 *
 * Everything else (name, autoComplete, required, minLength...) is passed
 * straight to the <input>, so the browser's saved-password offer keeps
 * working exactly as before. The button is a real button: reachable with
 * Tab, toggled with Enter or Space, and it never submits the form.
 */
export default function PasswordInput({ wrapperClassName = "relative mb-4", className = "", ...inputProps }: Props) {
  const [visible, setVisible] = useState(false);

  return (
    <div className={wrapperClassName}>
      <input
        {...inputProps}
        type={visible ? "text" : "password"}
        // Room on the right so long passwords do not run under the button.
        className={`${className} pr-11`}
      />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        aria-label={visible ? "Hide password" : "Show password"}
        aria-pressed={visible}
        title={visible ? "Hide password" : "Show password"}
        className="absolute inset-y-0 right-0 flex w-11 items-center justify-center rounded-r text-gray-500 hover:text-gray-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="h-5 w-5"
          aria-hidden="true"
        >
          <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z" />
          <circle cx="12" cy="12" r="3" />
          {/* A line through the eye while the password is showing: pressing hides it. */}
          {visible && <path d="M4 4l16 16" />}
        </svg>
      </button>
    </div>
  );
}
