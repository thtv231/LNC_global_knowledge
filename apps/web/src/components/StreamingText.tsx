interface Props {
  content: string;
  isStreaming: boolean;
}

export function StreamingText({ content, isStreaming }: Props) {
  return (
    <div className="whitespace-pre-wrap leading-relaxed">
      {content}
      {isStreaming && (
        <span className="inline-block w-2 h-4 ml-0.5 bg-current animate-pulse rounded-sm" />
      )}
    </div>
  );
}
