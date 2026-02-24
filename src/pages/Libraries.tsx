import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchLibraries, createLibrary, buildLibrary, archiveLibrary, deleteLibrary, fetchBuildStatus, fetchLibrarySections, type LibraryInfo, type LibrarySectionInfo } from "@/lib/api";
import { FloatingHeader } from "@/components/layout/FloatingHeader";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { Plus, Archive, Trash2, Eye, BookOpen, Loader2, ChevronUp } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useToast } from "@/hooks/use-toast";

const STATUS_BADGE: Record<string, { label: string; cls: string }> = {
  draft: { label: "Concept", cls: "bg-muted text-muted-foreground" },
  building: { label: "Opbouwen...", cls: "bg-warning/20 text-warning" },
  active: { label: "Actief", cls: "bg-success/20 text-success" },
  archived: { label: "Gearchiveerd", cls: "bg-muted text-muted-foreground" },
};

export default function Libraries() {
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);
  const [createOpen, setCreateOpen] = useState(false);
  const [sectionsOpen, setSectionsOpen] = useState<string | null>(null);
  const [sections, setSections] = useState<LibrarySectionInfo[]>([]);
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const navigate = useNavigate();

  const { data: libraries = [], isLoading } = useQuery({
    queryKey: ["libraries", statusFilter],
    queryFn: () => fetchLibraries(statusFilter),
  });

  const archiveMutation = useMutation({
    mutationFn: archiveLibrary,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["libraries"] }); toast({ title: "Bibliotheek gearchiveerd" }); },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteLibrary,
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["libraries"] }); toast({ title: "Bibliotheek verwijderd" }); },
    onError: (err: Error) => { toast({ title: "Fout", description: err.message, variant: "destructive" }); },
  });

  const handleViewSections = async (libraryId: string) => {
    if (sectionsOpen === libraryId) { setSectionsOpen(null); return; }
    try { const data = await fetchLibrarySections(libraryId); setSections(data); setSectionsOpen(libraryId); }
    catch { toast({ title: "Kon secties niet laden", variant: "destructive" }); }
  };
  return (
    <div className="min-h-screen bg-background relative">
      <div className="ambient-bg" aria-hidden="true"><div className="gradient-orb orb-1" /><div className="gradient-orb orb-2" /></div>
      <FloatingHeader onSettingsClick={() => {}} onHelpClick={() => {}} />
      <main className="container max-w-6xl mx-auto px-4 pb-12 relative z-10">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-foreground">Product Bibliotheken</h1>
            <p className="text-sm text-muted-foreground mt-1">Beheer voorwaarden-bibliotheken voor snellere analyses</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => navigate("/")}>Terug naar Analyse</Button>
            <Button size="sm" onClick={() => setCreateOpen(true)}><Plus className="w-4 h-4 mr-1" /> Nieuwe Bibliotheek</Button>
          </div>
        </div>
        <div className="flex gap-2 mb-4">
          {([undefined, "active", "draft", "building", "archived"] as const).map((s) => (
            <button key={s ?? "all"} onClick={() => setStatusFilter(s)}
              className={cn("px-3 py-1.5 rounded-full text-xs font-medium transition-colors", statusFilter === s ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:bg-muted/80")}
            >{s === undefined ? "Alle" : STATUS_BADGE[s]?.label ?? s}</button>
          ))}
        </div>
        <div className="floating-card overflow-hidden">
          {isLoading ? (
            <div className="p-12 text-center"><Loader2 className="w-6 h-6 animate-spin mx-auto text-muted-foreground" /></div>
          ) : libraries.length === 0 ? (
            <div className="p-12 text-center text-muted-foreground"><BookOpen className="w-10 h-10 mx-auto mb-3 opacity-40" /><p>Geen bibliotheken gevonden</p></div>
          ) : (
            <table className="w-full">
              <thead><tr className="bg-muted/50">
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground">Naam</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground">Verzekeraar</th>
                <th className="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wider text-muted-foreground">Versie</th>
                <th className="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wider text-muted-foreground">Status</th>
                <th className="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wider text-muted-foreground">Secties</th>
                <th className="px-4 py-3 text-center text-xs font-semibold uppercase tracking-wider text-muted-foreground">Clausules</th>
                <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground">Acties</th>
              </tr></thead>
              <tbody className="divide-y divide-border/50">
                {libraries.map((lib) => {
                  const badge = STATUS_BADGE[lib.status] ?? STATUS_BADGE.draft;
                  return (<>
                    <tr key={lib.id} className="hover:bg-muted/30 transition-colors">
                      <td className="px-4 py-3"><span className="text-sm font-medium">{lib.naam}</span>{lib.beschrijving && <p className="text-xs text-muted-foreground line-clamp-1 mt-0.5">{lib.beschrijving}</p>}</td>
                      <td className="px-4 py-3 text-sm text-muted-foreground">{lib.verzekeraar || "—"}</td>
                      <td className="px-4 py-3 text-center text-sm">{lib.versie || "—"}</td>
                      <td className="px-4 py-3 text-center"><Badge variant="secondary" className={cn("text-xs", badge.cls)}>{lib.status === "building" ? badge.label + " " + lib.build_progress + "%" : badge.label}</Badge></td>
                      <td className="px-4 py-3 text-center text-sm font-medium">{lib.section_count}</td>
                      <td className="px-4 py-3 text-center text-sm font-medium">{lib.clause_count}</td>
                      <td className="px-4 py-3"><div className="flex justify-end gap-1">
                        {lib.status === "active" && <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => handleViewSections(lib.id)} title="Secties bekijken">{sectionsOpen === lib.id ? <ChevronUp className="w-4 h-4" /> : <Eye className="w-4 h-4" />}</Button>}
                        {lib.status === "active" && <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => archiveMutation.mutate(lib.id)} title="Archiveren"><Archive className="w-4 h-4" /></Button>}
                        {lib.status === "draft" && <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive" onClick={() => deleteMutation.mutate(lib.id)} title="Verwijderen"><Trash2 className="w-4 h-4" /></Button>}
                      </div></td>
                    </tr>
                    {sectionsOpen === lib.id && (<tr key={lib.id + "-sec"}><td colSpan={7} className="px-4 py-3 bg-muted/30">
                      <div className="space-y-2 max-h-80 overflow-y-auto">
                        {sections.length === 0 ? <p className="text-sm text-muted-foreground">Geen secties gevonden</p> : sections.map((s) => (
                          <div key={s.id} className="p-3 rounded-lg bg-card border border-border/30">
                            <div className="flex items-center gap-2 mb-1">
                              {s.artikel_nummer && <Badge variant="outline" className="text-xs">{s.artikel_nummer}</Badge>}
                              {s.artikel_titel && <span className="text-sm font-medium">{s.artikel_titel}</span>}
                              {s.has_embedding && <Badge variant="secondary" className="text-xs bg-success/20 text-success">Embedding</Badge>}
                            </div>
                            <p className="text-xs text-muted-foreground line-clamp-2">{s.ruwe_tekst}</p>
                          </div>
                        ))}
                      </div>
                    </td></tr>)}
                  </>);
                })}
              </tbody>
            </table>
          )}
        </div>
        <CreateLibraryDialog open={createOpen} onOpenChange={setCreateOpen} />
      </main>
    </div>
  );
}

function CreateLibraryDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const [naam, setNaam] = useState("");
  const [verzekeraar, setVerzekeraar] = useState("");
  const [versie, setVersie] = useState("");
  const [beschrijving, setBeschrijving] = useState("");
  const [conditionsFiles, setConditionsFiles] = useState<File[]>([]);
  const [clauseFiles, setClauseFiles] = useState<File[]>([]);
  const [building, setBuilding] = useState(false);
  const [buildProgress, setBuildProgress] = useState(0);
  const [buildMessage, setBuildMessage] = useState("");
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const handleCreate = async () => {
    if (!naam.trim()) return;
    try {
      const formData = new FormData();
      formData.append("naam", naam);
      if (verzekeraar) formData.append("verzekeraar", verzekeraar);
      if (versie) formData.append("versie", versie);
      if (beschrijving) formData.append("beschrijving", beschrijving);
      const library = await createLibrary(formData);
      if (conditionsFiles.length > 0 || clauseFiles.length > 0) {
        const buildData = new FormData();
        conditionsFiles.forEach((f) => buildData.append("conditions_files", f));
        clauseFiles.forEach((f) => buildData.append("clause_files", f));
        await buildLibrary(library.id, buildData);
        setBuilding(true);
        const interval = setInterval(async () => {
          try {
            const status = await fetchBuildStatus(library.id);
            setBuildProgress(status.build_progress);
            setBuildMessage(status.build_message || "");
            if (status.status === "active" || status.status === "draft") {
              clearInterval(interval); setBuilding(false);
              queryClient.invalidateQueries({ queryKey: ["libraries"] });
              onOpenChange(false); resetForm();
              toast({ title: status.status === "active" ? "Bibliotheek opgebouwd!" : "Build mislukt", description: status.build_message || undefined, variant: status.status === "active" ? "default" : "destructive" });
            }
          } catch { clearInterval(interval); setBuilding(false); }
        }, 2000);
      } else {
        queryClient.invalidateQueries({ queryKey: ["libraries"] });
        onOpenChange(false); resetForm();
        toast({ title: "Bibliotheek aangemaakt (concept)" });
      }
    } catch (err) {
      toast({ title: "Fout", description: err instanceof Error ? err.message : "Onbekende fout", variant: "destructive" });
    }
  };

  const resetForm = () => { setNaam(""); setVerzekeraar(""); setVersie(""); setBeschrijving(""); setConditionsFiles([]); setClauseFiles([]); setBuildProgress(0); setBuildMessage(""); };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader><DialogTitle>Nieuwe Bibliotheek</DialogTitle></DialogHeader>
        <div className="space-y-4">
          <div>
            <label className="text-sm font-medium">Naam *</label>
            <input value={naam} onChange={(e) => setNaam(e.target.value)} placeholder="bijv. Collectieve Ongevallen"
              className="w-full mt-1 px-3 py-2 rounded-xl border border-border/50 bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-sm font-medium">Verzekeraar</label>
              <input value={verzekeraar} onChange={(e) => setVerzekeraar(e.target.value)} placeholder="bijv. Allianz"
                className="w-full mt-1 px-3 py-2 rounded-xl border border-border/50 bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" />
            </div>
            <div>
              <label className="text-sm font-medium">Versie</label>
              <input value={versie} onChange={(e) => setVersie(e.target.value)} placeholder="bijv. 2025-Q1"
                className="w-full mt-1 px-3 py-2 rounded-xl border border-border/50 bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" />
            </div>
          </div>
          <div>
            <label className="text-sm font-medium">Beschrijving</label>
            <textarea value={beschrijving} onChange={(e) => setBeschrijving(e.target.value)} rows={2}
              className="w-full mt-1 px-3 py-2 rounded-xl border border-border/50 bg-background text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary/30" />
          </div>
          <div>
            <label className="text-sm font-medium">Algemene voorwaarden</label>
            <p className="text-xs text-muted-foreground mt-0.5 mb-1">PDF, Word of TXT — de polisvoorwaarden van het product</p>
            <input type="file" multiple accept=".pdf,.docx,.doc,.txt" onChange={(e) => setConditionsFiles(Array.from(e.target.files || []))}
              className="w-full mt-1 text-sm file:mr-3 file:py-1.5 file:px-3 file:rounded-full file:border-0 file:text-sm file:bg-primary/10 file:text-primary hover:file:bg-primary/20" />
            {conditionsFiles.length > 0 && (
              <p className="text-xs text-muted-foreground mt-1">{conditionsFiles.length} bestand{conditionsFiles.length !== 1 ? "en" : ""} geselecteerd</p>
            )}
          </div>
          <div>
            <label className="text-sm font-medium">Clausulebibliotheek</label>
            <p className="text-xs text-muted-foreground mt-0.5 mb-1">PDF, Word, Excel of CSV — ook honderden losse bestanden mogelijk</p>
            <input type="file" multiple accept=".pdf,.docx,.doc,.txt,.xlsx,.xls,.csv" onChange={(e) => setClauseFiles(Array.from(e.target.files || []))}
              className="w-full mt-1 text-sm file:mr-3 file:py-1.5 file:px-3 file:rounded-full file:border-0 file:text-sm file:bg-primary/10 file:text-primary hover:file:bg-primary/20" />
            {clauseFiles.length > 0 && (
              <p className="text-xs text-muted-foreground mt-1">{clauseFiles.length} bestand{clauseFiles.length !== 1 ? "en" : ""} geselecteerd</p>
            )}
          </div>
          {building && (
            <div className="space-y-2">
              <div className="flex justify-between text-xs text-muted-foreground"><span>{buildMessage}</span><span>{buildProgress}%</span></div>
              <div className="h-2 rounded-full bg-muted overflow-hidden"><div className="h-full bg-primary rounded-full transition-all duration-500" style={{ width: buildProgress + "%" }} /></div>
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={building}>Annuleren</Button>
          <Button onClick={handleCreate} disabled={!naam.trim() || building}>
            {building ? <><Loader2 className="w-4 h-4 animate-spin mr-1" />Opbouwen...</> : conditionsFiles.length > 0 || clauseFiles.length > 0 ? "Aanmaken & Bouwen" : "Aanmaken als Concept"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
