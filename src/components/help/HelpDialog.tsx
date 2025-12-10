import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";

interface HelpDialogProps {
  open: boolean;
  onClose: () => void;
}

export const HelpDialog = ({ open, onClose }: HelpDialogProps) => {
  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent className="floating-card max-w-2xl max-h-[80vh] overflow-auto custom-scrollbar">
        <DialogHeader>
          <DialogTitle className="text-xl font-semibold text-foreground">
            Hoe werkt de VB Converter?
          </DialogTitle>
        </DialogHeader>

        <div className="mt-4 space-y-6">
          <p className="text-muted-foreground">
            De VB Converter helpt u bij het analyseren en standaardiseren van vrije polisteksten.
            Upload uw bestanden en laat de tool automatisch clusters maken en adviezen genereren.
          </p>

          <Accordion type="single" collapsible className="w-full">
            <AccordionItem value="step-1">
              <AccordionTrigger className="text-sm font-medium">
                Stap 1: Upload Polisbestand
              </AccordionTrigger>
              <AccordionContent className="text-sm text-muted-foreground">
                Sleep uw Excel- of CSV-export met vrije teksten naar het eerste vak.
                De tool herkent automatisch kolommen zoals 'Tekst' of 'Vrije Tekst'.
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="step-2">
              <AccordionTrigger className="text-sm font-medium">
                Stap 2: Upload Voorwaarden
              </AccordionTrigger>
              <AccordionContent className="text-sm text-muted-foreground">
                Dit is de belangrijkste stap! De tool vergelijkt elke vrije tekst tegen
                de geüploade voorwaarden om te bepalen of de tekst al gedekt is.
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="step-3">
              <AccordionTrigger className="text-sm font-medium">
                Stap 3: Configureer Instellingen
              </AccordionTrigger>
              <AccordionContent className="text-sm text-muted-foreground">
                Pas de cluster nauwkeurigheid, minimum frequentie en window size aan
                naar uw wensen via het instellingen menu.
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="step-4">
              <AccordionTrigger className="text-sm font-medium">
                Stap 4: Start Analyse
              </AccordionTrigger>
              <AccordionContent className="text-sm text-muted-foreground">
                Klik op 'Start Analyse' om het proces te starten. De tool clustert,
                vergelijkt en genereert adviezen automatisch.
              </AccordionContent>
            </AccordionItem>
          </Accordion>

          <div className="pt-4 border-t border-border">
            <h4 className="font-medium text-foreground mb-4">Advies Types</h4>
            <div className="grid grid-cols-2 gap-3">
              <div className="flex items-center gap-2">
                <Badge className="badge-verwijderen">Verwijderen</Badge>
                <span className="text-xs text-muted-foreground">Gedekt in voorwaarden</span>
              </div>
              <div className="flex items-center gap-2">
                <Badge className="badge-splitsen">Splitsen</Badge>
                <span className="text-xs text-muted-foreground">Meerdere clausules</span>
              </div>
              <div className="flex items-center gap-2">
                <Badge className="badge-standaardiseren">Standaardiseren</Badge>
                <span className="text-xs text-muted-foreground">Vaak voorkomend</span>
              </div>
              <div className="flex items-center gap-2">
                <Badge className="badge-behouden">Behouden</Badge>
                <span className="text-xs text-muted-foreground">Specifieke afwijking</span>
              </div>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};
