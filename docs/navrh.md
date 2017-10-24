# <h1> Návrh zadania
Článok opisuje systém ARES, ktorý má vlastný (upravený) algoritmus na opravu chýb (Failure Recovery) pri OpenFlow verzií 1.3 a 1.0. Výstupom algoritmu je, že každý prepínač pozná hlavnú a všetky záložné cesty v prípade výpadku hlavnej cesty.
V našom návrhu by sme chceli porovnať výsledky tohto algoritmu s RSTP za použitia GEESE generátora premávky a zhodnotiť zistené výsledky. V článku sú porovnané výsledky času obnovenia v ring topológii pri 4,6,8,10 a 12 prepínačoch. Pričom by sme chceli simulovať so všetkými spomínanými počtami prepínačov a zhodnotiť výsledky podľa obrázka zobrazeného nižšie.
Pričom čas obnovy sa počítal pomocou , kde  je čas prenosu správy z A do B počas výpadku a  je čas prenosu tej istej správy ale pri normálnych podmienkach.

![Čas obnovy v ring topológií](recTime.PNG)

Návrh topológie je znázornený v obrázku nižšie. Topológia sa skladá zo 4 až 12 prepínačov (pričom budeme simulovať na 4,6,8,10 a 12 prepínačoch) a  RYU kontroléra. Na prepínačoch sú rovnomerne rozdelené koncové zariadenia, pričom dve zariadenia (pri scenári so 4 prepínačmi) patria do rovnakej multicast skupiny (celkovo 5 rôznych multicast skupín). Pričom testovanie času obnovy pri RSTP je možné len pri ring topológii.

![Návrh topológie](topology.png)

## <h2> Testovanie:
Topológiu budeme testovať podľa článku, kde testovanie prebiehalo nasledovne: Generátor premávky GEESE bol spustený po stabilizácii siete. Sieťové zlyhania boli generované 60 sekúnd po začiatku emulácie (náhodné vypnutie linku pomocou linuxového príkazu). Menili sa parametre ako počet koncových zariadení, počet prepínačov a počet koncových zariadení pre multicast skupinu.


