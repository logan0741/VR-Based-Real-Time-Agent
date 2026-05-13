type SetControlProps = {
  count: number;
  onChange: (delta: number) => void;
};

export default function SetControl({ count, onChange }: SetControlProps) {
  return (
    <div className="set-row">
      <span className="set-label">세트 수</span>
      <button className="set-btn" type="button" onClick={() => onChange(-1)}>
        −
      </button>
      <span className="set-count">{count}</span>
      <button className="set-btn" type="button" onClick={() => onChange(1)}>
        +
      </button>
    </div>
  );
}
