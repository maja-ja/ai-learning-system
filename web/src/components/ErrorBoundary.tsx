import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle, RotateCcw } from "lucide-react";

type Props = { children: ReactNode; fallbackMessage?: string };
type State = { hasError: boolean; error: Error | null };

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="border-2 border-black p-6 space-y-4 max-w-lg mx-auto mt-12">
          <div className="flex items-center gap-3">
            <AlertTriangle className="h-6 w-6 shrink-0" />
            <h2 className="text-lg font-bold">出了點問題</h2>
          </div>
          <p className="text-sm text-gray-600">
            {this.props.fallbackMessage || "此區塊發生錯誤，請重試或重新整理頁面。"}
          </p>
          {this.state.error && (
            <pre className="text-xs text-gray-500 bg-gray-50 p-3 border border-black/10 overflow-auto max-h-32">
              {this.state.error.message}
            </pre>
          )}
          <button
            type="button"
            onClick={() => this.setState({ hasError: false, error: null })}
            className="inline-flex items-center gap-2 border border-black px-4 py-2 text-sm font-medium"
          >
            <RotateCcw className="h-4 w-4" />
            重試
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
