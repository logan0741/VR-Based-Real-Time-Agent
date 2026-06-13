type FeedbackChipProps = {
  status: 'ok' | 'warn';
  message: string;
};

export default function FeedbackChip({ status, message }: FeedbackChipProps) {
  return (
    <div className={`fb-chip fb-${status}`}>
      <span className="fb-dot" />
      {message}
    </div>
  );
}
