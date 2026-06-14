type SetControlProps = {
  count: number;
  label: string;
  decreaseLabel: string;
  increaseLabel: string;
  onChange: (delta: number) => void;
};

export default function SetControl({
  count,
  label,
  decreaseLabel,
  increaseLabel,
  onChange,
}: SetControlProps) {
  return (
    <div className="set-row">
      <span className="set-label">{label}</span>
      <button className="set-btn" type="button" onClick={() => onChange(-1)} aria-label={decreaseLabel}>
        -
      </button>
      <span className="set-count">{count}</span>
      <button className="set-btn" type="button" onClick={() => onChange(1)} aria-label={increaseLabel}>
        +
      </button>
    </div>
  );
}
