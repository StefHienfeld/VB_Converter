import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface HelpDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export const HelpDialog = ({ open, onOpenChange }: HelpDialogProps) => {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="floating-card max-w-2xl max-h-[80vh] overflow-auto custom-scrollbar">
        <DialogHeader>
          <DialogTitle className="text-xl font-semibold text-foreground">
            Hoe werkt de VB Converter?
          </DialogTitle>
        </DialogHeader>

        <div className="mt-4 space-y-6">
          <p className="text-muted-foreground">
            De VB Converter helpt bij het analyseren en standaardiseren van vrije polisteksten.
            Upload de bestanden en laat de tool automatisch clusters maken en adviezen genereren.
          </p>

          <div className="space-y-5">
            <div>
              <h4 className="text-sm font-semibold text-foreground mb-2">
                Stap 1: Upload Polisbestand
              </h4>
              <p className="text-sm text-muted-foreground">
                Sleep een Excel- of CSV-export met vrije teksten naar het eerste vak.
                De tool herkent automatisch kolommen zoals 'Tekst' of 'Vrije Tekst'.
              </p>
            </div>

            <div>
              <h4 className="text-sm font-semibold text-foreground mb-2">
                Stap 2: Upload Voorwaarden
              </h4>
              <p className="text-sm text-muted-foreground">
                Dit is een belangrijke stap. De tool vergelijkt elke vrije tekst tegen
                de geüploade voorwaarden om te bepalen of de tekst al gedekt is.
              </p>
            </div>

            <div>
              <h4 className="text-sm font-semibold text-foreground mb-2">
                Stap 3: Configureer Instellingen
              </h4>
              <p className="text-sm text-muted-foreground">
                Pas de cluster nauwkeurigheid, minimum frequentie en window size aan
                via het instellingen menu (tandwiel icoon rechtsboven).
              </p>
            </div>

            <div>
              <h4 className="text-sm font-semibold text-foreground mb-2">
                Stap 4: Start Analyse
              </h4>
              <p className="text-sm text-muted-foreground">
                Klik op 'Start Analyse' om het proces te starten. De tool clustert,
                vergelijkt en genereert adviezen automatisch.
              </p>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};
