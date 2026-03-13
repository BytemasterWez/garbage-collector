type SearchBoxProps = {
  query: string;
  onQueryChange: (value: string) => void;
};

export function SearchBox({ query, onQueryChange }: SearchBoxProps) {
  return (
    <div className="search-box">
      <label className="field-label" htmlFor="search-input">
        Keyword search
      </label>
      <input
        id="search-input"
        className="search-input"
        type="search"
        value={query}
        onChange={(event) => onQueryChange(event.target.value)}
        placeholder="Search title or content"
      />
    </div>
  );
}
