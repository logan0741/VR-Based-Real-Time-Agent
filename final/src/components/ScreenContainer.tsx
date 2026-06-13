import type { ReactNode } from 'react';

type ScreenContainerProps = {
  active: boolean;
  id: string;
  children: ReactNode;
};

export default function ScreenContainer({ active, id, children }: ScreenContainerProps) {
  return (
    <div className={`screen ${active ? 'active' : ''}`} id={id}>
      {children}
    </div>
  );
}
