type RenderSlotProps = {
  id: string;
  label: string;
};

export default function RenderSlot({ id, label }: RenderSlotProps) {
  return (
    <div className="render-slot" id={id}>
      {label}
    </div>
  );
}
