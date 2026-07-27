import { StrictMode, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { fetchProducts, type Product } from "./catalog";
import "./styles.css";

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

function ProductSummary({ product }: { product: Product }) {
  return (
    <>
      <div className="selectionImage">
        <img src={product.image_src} alt={product.name} loading="lazy" />
      </div>
      <div className="selectionDetails">
        <strong>{product.name}</strong>
        <span>
          {[product.category, formatPrice(product.price)].filter(Boolean).join(" · ")}
        </span>
      </div>
    </>
  );
}

function CatalogApp() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("all");

  useEffect(() => {
    fetchProducts()
      .then((items) => setProducts(items))
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

const acceptedImageTypes = ["image/jpeg", "image/png", "image/webp"];

function DesignerApp() {
  const [image, setImage] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [instructions, setInstructions] = useState("");
  const [resultUrl, setResultUrl] = useState("");
  const [resultMessage, setResultMessage] = useState("");
  const [products, setProducts] = useState<Product[]>([]);
  const [productsLoading, setProductsLoading] = useState(true);
  const [productsError, setProductsError] = useState("");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [selectionNotice, setSelectionNotice] = useState("");
  const [resultProducts, setResultProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!image) {
      setPreviewUrl("");
      return;
    }
    const nextUrl = URL.createObjectURL(image);
    setPreviewUrl(nextUrl);
    return () => URL.revokeObjectURL(nextUrl);
  }, [image]);

  useEffect(() => {
    fetchProducts()
      .then((items) => {
        const selectable = items.filter((product) => product.id && product.image_src);
        setProducts(selectable);
        if (selectable.length === 0) {
          setProductsError("No selectable catalog products are available.");
        }
      })
      .catch(() => setProductsError("The product catalog could not be loaded."))
      .finally(() => setProductsLoading(false));
  }, []);

  const selectedProducts = useMemo(
    () => selectedIds.map((id) => products.find((product) => product.id === id)).filter(Boolean) as Product[],
    [products, selectedIds],
  );

  function toggleProduct(product: Product) {
    setResultUrl("");
    setResultMessage("");
    setResultProducts([]);
    setError("");
    if (selectedIds.includes(product.id)) {
      setSelectedIds(selectedIds.filter((id) => id !== product.id));
      setSelectionNotice("");
      return;
    }
    if (selectedIds.length >= 10) {
      setSelectionNotice("You can include up to ten products.");
      return;
    }
    setSelectedIds([...selectedIds, product.id]);
    setSelectionNotice("");
  }

  function selectImage(file: File | undefined) {
    setError("");
    setResultUrl("");
    setResultMessage("");
    if (!file) {
      setImage(null);
      return;
    }
    if (!acceptedImageTypes.includes(file.type)) {
      setImage(null);
      setError("Please choose a JPG, PNG, or WEBP image.");
      return;
    }
    if (file.size > 15 * 1024 * 1024) {
      setImage(null);
      setError("Please choose an image smaller than 15 MB.");
      return;
    }
    setImage(file);
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!image || loading) {
      setError("Please select a room image first.");
      return;
    }
    if (selectedIds.length < 1) {
      setError("Please select at least one product to include.");
      return;
    }

    setLoading(true);
    setError("");
    setResultUrl("");
    setResultMessage("");

    try {
      const response = await fetch("/api/redesign", {
        method: "POST",
        headers: {
          "Content-Type": image.type,
          "X-File-Name": encodeURIComponent(image.name),
          "X-Design-Instructions": encodeURIComponent(instructions),
          "X-Product-Ids": encodeURIComponent(JSON.stringify(selectedIds)),
        },
        body: image,
      });
      const payload = (await response.json()) as {
        imageUrl?: string;
        error?: string;
        message?: string;
      };
      if (!response.ok || !payload.imageUrl) {
        throw new Error(payload.error ?? "We couldn't redesign this room. Please try again.");
      }
      setResultUrl(payload.imageUrl);
      setResultMessage(payload.message ?? "");
      setResultProducts(selectedProducts);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "We couldn't redesign this room. Please try again.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="designerShell">
      <header className="designerHeader">
        <p className="eyebrow">Modern Grace &amp; Co.</p>
        <h1>Reimagine your room.</h1>
        <p>Upload a photo and see it transformed with our warm, refined point of view.</p>
      </header>

      <form className="designerForm" onSubmit={submit}>
        <label className={`uploadField ${previewUrl ? "hasImage" : ""}`}>
          <input
            type="file"
            accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"
            onChange={(event) => selectImage(event.target.files?.[0])}
          />
          {previewUrl ? (
            <img src={previewUrl} alt="Your selected room" />
          ) : (
            <span>
              <strong>Choose a room photo</strong>
              JPG, PNG, or WEBP · up to 15 MB
            </span>
          )}
          {previewUrl && <span className="changePhoto">Choose a different photo</span>}
        </label>

        <section className="productChooser" aria-labelledby="product-chooser-title">
          <div className="chooserHeading">
            <div>
              <h2 id="product-chooser-title">Choose products to include</h2>
              <p>Select one to ten products for your redesigned room.</p>
            </div>
            <strong>{selectedIds.length}/10 selected</strong>
          </div>

          {productsLoading && <p className="formNotice">Loading products…</p>}
          {productsError && <p className="formNotice errorNotice">{productsError}</p>}
          {!productsLoading && !productsError && (
            <div className="selectionGrid">
              {products.map((product) => {
                const selected = selectedIds.includes(product.id);
                const disabled = !selected && selectedIds.length >= 10;
                return (
                  <button
                    className={`selectionCard ${selected ? "selected" : ""}`}
                    type="button"
                    key={product.id}
                    aria-pressed={selected}
                    disabled={disabled}
                    onClick={() => toggleProduct(product)}
                  >
                    <ProductSummary product={product} />
                    <span className="selectionMark">{selected ? "Selected" : "Select"}</span>
                  </button>
                );
              })}
            </div>
          )}
          {(selectionNotice || selectedIds.length === 10) && (
            <p className="selectionNotice">
              {selectionNotice || "Maximum reached. Remove a product to choose another."}
            </p>
          )}
        </section>

        <label className="designerField">
          <span>What would you like to change?</span>
          <textarea
            value={instructions}
            maxLength={500}
            onChange={(event) => setInstructions(event.target.value)}
            placeholder="Optional — for example, make it warmer and add more layered lighting."
          />
        </label>

        {error && <p className="formNotice errorNotice" role="alert">{error}</p>}

        <button
          className="redesignButton"
          type="submit"
          disabled={!image || selectedIds.length === 0 || loading}
        >
          {loading ? "Designing your room…" : "Redesign this room"}
        </button>
      </form>

      {loading && (
        <section className="resultCard loadingCard" aria-live="polite">
          <span className="spinner" />
          <h2>Creating your new look</h2>
          <p>This can take a minute. Please keep this page open.</p>
        </section>
      )}

      {resultUrl && !loading && (
        <section className="resultCard" aria-live="polite">
          <p className="eyebrow">Your redesigned room</p>
          <img src={resultUrl} alt="Room redesigned in the Modern Grace and Co. aesthetic" />
          {resultMessage && <p className="mockNotice">{resultMessage}</p>}
          <div className="resultProducts">
            <h2>Products selected for this room</h2>
            <div className="selectionGrid resultSelectionGrid">
              {resultProducts.map((product) => (
                <article className="selectionCard selected" key={product.id}>
                  <ProductSummary product={product} />
                </article>
              ))}
            </div>
          </div>
        </section>
      )}

      <a className="catalogLink" href="/catalog">Browse the product catalog</a>
    </main>
  );
}

const App = window.location.pathname.startsWith("/catalog") ? CatalogApp : DesignerApp;

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
