export async function downloadPDF(
  reportElement: HTMLElement,
  filename: string,
): Promise<void> {
  const [{ default: jsPDF }, { default: html2canvas }] = await Promise.all([
    import("jspdf"),
    import("html2canvas"),
  ]);

  const canvas = await html2canvas(reportElement, {
    scale: 2,
    useCORS: true,
    logging: false,
    backgroundColor: "#ffffff",
  });

  const imgWidth = 210; // A4 width in mm
  const pageHeight = 297; // A4 height in mm
  const imgHeight = (canvas.height * imgWidth) / canvas.width;

  const pdf = new jsPDF("p", "mm", "a4");
  let heightLeft = imgHeight;
  let position = 0;

  pdf.addImage(
    canvas.toDataURL("image/png"),
    "PNG",
    0,
    position,
    imgWidth,
    imgHeight,
  );
  heightLeft -= pageHeight;

  while (heightLeft > 0) {
    position = -(imgHeight - heightLeft);
    pdf.addPage();
    pdf.addImage(
      canvas.toDataURL("image/png"),
      "PNG",
      0,
      position,
      imgWidth,
      imgHeight,
    );
    heightLeft -= pageHeight;
  }

  pdf.save(filename);
}
