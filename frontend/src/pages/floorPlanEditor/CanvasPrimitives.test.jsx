import React from 'react';
import { render, screen } from '@testing-library/react';

import { DeleteButton } from './CanvasPrimitives';

jest.mock('konva', () => ({
  Filters: {
    Grayscale: jest.fn(),
  },
}));

jest.mock('react-konva', () => {
  const ReactLocal = require('react');

  const createComponent = (name, renderText = false) => ReactLocal.forwardRef(({ children, text }, ref) => (
    <div ref={ref} data-konva={name}>
      {renderText ? text : children}
    </div>
  ));

  return {
    Group: createComponent('Group'),
    Circle: createComponent('Circle'),
    Image: createComponent('Image'),
    Line: createComponent('Line'),
    Rect: createComponent('Rect'),
    Text: createComponent('Text', true),
  };
});

test('delete button renders a vector cross instead of a broken text glyph', () => {
  const { container } = render(<DeleteButton x={0} y={0} onClick={() => {}} />);

  expect(container.querySelectorAll('[data-konva="Line"]')).toHaveLength(2);
  expect(screen.queryByText('Р“вЂ”')).not.toBeInTheDocument();
});
