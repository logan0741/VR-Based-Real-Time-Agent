import type { Exercise } from '../types';

type ExerciseSelectorProps = {
  options: Exercise[];
  selectedId: string;
  onSelect: (item: Exercise) => void;
};

export default function ExerciseSelector({ options, selectedId, onSelect }: ExerciseSelectorProps) {
  return (
    <div className="ex-cards">
      {options.map((option) => (
        <button
          key={option.id}
          type="button"
          className={`ex-card ${selectedId === option.id ? 'on' : ''}`}
          onClick={() => onSelect(option)}
        >
          <span className="ex-icon">{option.icon}</span>
          <span className="ex-label">{option.label}</span>
        </button>
      ))}
    </div>
  );
}
