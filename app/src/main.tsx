import { StrictMode, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

type Product = {
  name: string;
  description: string;
  sku: string;
  vendor_name: string;
  vendor_sku: string;
  brand: string;
  category: string;
  price: number | null;
  cost: number | null;
  width_in: number | null;
  depth_in: number | null;
  height_in: number | null;
  diameter_in: number | null;
  color: string;
  material: string;
  finish: string;
  room_tags: string[];
  style_tags: string[];
  product_tags: string[];
  general_tags: string[];
  image_url: string;
  image_src: string;
  active: boolean;
  notes: string;
};

function formatPrice(value: number | null): string {
  if (value === null) {
    return "";
  }

  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: value % 1 === 0 ? 0 : 2,
  }).format(value);
}

function productSearchText(product: Product): string {
  return [
    product.name,
    product.category,
    product.color,
    product.material,
    product.finish,
    product.room_tags.join(" "),
    product.style_tags.join(" "),
    product.product_tags.join(" "),
    product.general_tags.join(" "),
  ]
    .join(" ")
    .toLowerCase();
}

function tagList(product: Product): string[] {
  return [
    ...product.room_tags,
    ...product.style_tags,
    ...product.product_tags,
  ].filter(Boolean);
}

function App() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("all");

  useEffect(() => {
    fetch("/data/products.json")
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Could not load products.json (${response.status})`);
        }
        return response.json() as Promise<Product[]>;
      })
      .then((items) => {
        setProducts(items.filter((product) => product.active));
      })
      .catch((caught: unknown) => {
        setError(caught instanceof Error ? caught.message : "Could not load products.");
      })
      .finally(() => setLoading(false));
  }, []);

  const categories = useMemo(() => {
    return Array.from(
      new Set(products.map((product) => product.category).filter(Boolean)),
    ).sort((a, b) => a.localeCompare(b));
  }, [products]);

  const filteredProducts = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();

    return products.filter((product) => {
      const matchesCategory = category === "all" || product.category === category;
      const matchesQuery =
        normalizedQuery === "" || productSearchText(product).includes(normalizedQuery);

      return matchesCategory && matchesQuery;
    });
  }, [category, products, query]);

  return (
    <main className="shell">
      <header className="header">
        <p className="eyebrow">Modern Grace & Co.</p>
        <h1>Mogranco Catalog</h1>
        <p className="summary">
          {loading
            ? "Loading products"
            : `${filteredProducts.length} of ${products.length} products shown`}
        </p>
      </header>

      <section className="controls" aria-label="Product filters">
        <label className="field">
          <span>Search</span>
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Name, material, color, tag"
          />
        </label>

        <label className="field">
          <span>Category</span>
          <select value={category} onChange={(event) => setCategory(event.target.value)}>
            <option value="all">All categories</option>
            {categories.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>
      </section>

      {error && <p className="notice">{error}</p>}
      {loading && <p className="notice">Loading catalog data...</p>}

      {!loading && !error && filteredProducts.length === 0 && (
        <p className="notice">No products match those filters.</p>
      )}

      <section className="grid" aria-label="Products">
        {filteredProducts.map((product) => (
          <article className="card" key={`${product.sku}-${product.name}`}>
            <div className="imageWrap">
              {product.image_src ? (
                <img src={product.image_src} alt={product.name} loading="lazy" />
              ) : (
                <div className="imageFallback">No image</div>
              )}
            </div>

            <div className="cardBody">
              <div className="cardTopline">
                <span>{product.category || "Uncategorized"}</span>
                <strong>{formatPrice(product.price)}</strong>
              </div>
              <h2>{product.name}</h2>

              <div className="meta">
                {[product.color, product.material, product.finish].filter(Boolean).join(" / ")}
              </div>

              {tagList(product).length > 0 && (
                <div className="tags" aria-label="Product tags">
                  {tagList(product)
                    .slice(0, 5)
                    .map((tag) => (
                      <span key={tag}>{tag}</span>
                    ))}
                </div>
              )}
            </div>
          </article>
        ))}
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
