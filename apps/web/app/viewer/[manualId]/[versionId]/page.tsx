import { ViewerShell } from "../../../../components/viewer-shell";

type ViewerPageProps = {
  params: Promise<{
    manualId: string;
    versionId: string;
  }>;
  searchParams: Promise<{
    page?: string;
    section?: string;
  }>;
};

export default async function ViewerPage({ params, searchParams }: ViewerPageProps) {
  const resolvedParams = await params;
  const resolvedSearchParams = await searchParams;

  return (
    <ViewerShell
      manualId={resolvedParams.manualId}
      page={resolvedSearchParams.page ?? "-"}
      section={resolvedSearchParams.section ?? "-"}
      versionId={resolvedParams.versionId}
    />
  );
}
