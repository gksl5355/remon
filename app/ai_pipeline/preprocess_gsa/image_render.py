from pathlib import Path
import fitz  # PyMuPDF

def render_pdf_to_images(
    pdf_path: str,
    output_dir: str,
    dpi: int = 200,
    image_format: str = "png",
) -> list[str]:
    """
    PDF 파일을 페이지별 이미지로 렌더링하고, 저장된 이미지 경로 리스트를 반환한다.

    Args:
        pdf_path: 렌더링할 PDF 파일 경로
        output_dir: 이미지가 저장될 디렉터리
        dpi: 렌더링 해상도 (기본 200, 300 이상이면 꽤 선명)
        image_format: "png", "jpg" 등

    Returns:
        저장된 이미지 파일 경로(str) 리스트 (페이지 순서대로)
    """
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    doc = fitz.open(pdf_path)
    saved_paths: list[str] = []

    # PyMuPDF 기본 해상도는 72dpi라서, dpi 비율만큼 확대
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)

    for page_index in range(len(doc)):
        page = doc.load_page(page_index)
        pix = page.get_pixmap(matrix=matrix, alpha=False)

        filename = f"{pdf_path.stem}_p{page_index + 1:03d}.{image_format}"
        out_path = output_dir / filename

        pix.save(out_path.as_posix())
        saved_paths.append(str(out_path))

    doc.close()
    return saved_paths


if __name__ == "__main__":
    # 예시 사용법
    pdf = "/Users/broccoli/Desktop/remon/app/ai_pipeline/preprocess_gsa/사용데이터/practice_pdf.pdf"     # 실제 PDF 경로
    out_dir = "output/pdf_images"        # 저장할 폴더

    paths = render_pdf_to_images(pdf, out_dir, dpi=200)
    print("Saved images:")
    for p in paths:
        print("  -", p)
