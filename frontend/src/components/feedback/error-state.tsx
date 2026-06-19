export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4">
      <div className="text-sm font-semibold text-red-900">Unable to load data</div>
      <p className="mt-1 text-sm text-red-700">{message}</p>
      {onRetry ? (
        <button
          className="mt-3 text-sm font-medium text-red-900 underline"
          onClick={onRetry}
          type="button"
        >
          Try again
        </button>
      ) : null}
    </div>
  );
}

