import { ReactNode } from 'react';

type RenderSlotProps = {
  id: string;
  label: string;
  children?: ReactNode;
};

export default function RenderSlot({ id, label, children }: RenderSlotProps) {
  return (
    <div className="render-slot" id={id}>
      {children ?? label}
    </div>
  );
}
