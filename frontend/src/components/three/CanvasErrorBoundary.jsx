import { Component } from 'react';

export default class CanvasErrorBoundary extends Component {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error) {
    console.warn('[صنّعها] 3D scene unavailable, showing static render.', error);
  }

  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}
