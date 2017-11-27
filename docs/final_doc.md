# <h1> Analýza

# <h1> Návrh

## <h2> Topológie
Topológie boli vytvorené podľa testovacích scenárov v článku, kde sa všetky experimenty vykonávali na kruhových a „mesh“ topológiách,
z ktorých sme sa rozhodli implementovať práve kruhové topológie, nakoľko nám prišlo testovanie v takomto prostredí náročnejšie, 
keďže veľa controllerov nemá podporu pre loop-handling. Je tak celkom bežné, že v takejto situácií sieť nefunguje ako má, pretože sú
všetky pakety zachytené v slučke.

Všetky topológie obsahujú 10 hostov, rozdelených do piatich rôznych multicast skupín. Počet switchov sa mení – 
4, 8 a 12 switchov. Medzi nich sme rovnomerne rozmiestnili jednotlivých hostov. 

Topológie sú implementované v skriptoch, pomocou jazyka python. Samotný súbor sa spúšťa po spustení controllera, príkazom:
* sudo python topoX.py , kde X môže nadobúdať hodnoty 1 - 3, v závislosti od topológie, ktorá sa má spustiť

Pred spustením celej topológie však ešte premazávame topológie v mininete (sudo mn -c), aby sme sa uistili, že sa v nej budú 
nachádzať len pre nás potrebné informácie a dáta. Ďalej sa pri vytváraní topológií postupuje nasledovne: 
* Vytvorenie siete s remote controllerom 
    + net = Mininet(controller=RemoteController)

* Pridanie hostov, ktorí majú definovaný názov, MAC adresu a IP adresu
    + h0 = net.addHost(&quot;h0&quot;, mac=&quot;00:00:00:00:00:01&quot;, ip=&quot;10.0.0.1/24&quot;)
    
* Pridanie switchov, ktoré majú definovaný názov, ID a protokol
    + s0 = net.addSwitch(&quot;s0&quot;,dpid=&quot;0000000000000001&quot;,protocols=&quot;OpenFlow13&quot;)

* Pridanie potrebných liniek
    + net.addLink(s0,h0)

* Pridanie controllera
    + c0 = net.addController(&quot;c0&quot;)

* Spustenie siete
    + net.start()
    
* Spustenie RSTP protokolu na jednotlivých switchoch
    + for x in range(0,4 2 ):
      + cmd = &quot;ovs-vsctl set bridge s%d rstp_enable=true&quot; % (x)
      + c0.cmd(cmd)

* Pridanie jednotlivých multicast skupín
    + cmd=&quot;ip route add 225.0.0.1 dev h0-eth0&quot;
    + h0.cmd(cmd)

* Spustenie CLI
    + CLI(net)

* Zastavenie siete
    + net.stop
    

# <h1> Implementácia

## <h2> Multicast

## <h2> Geese

## <h2> RSTP
Ako už bolo spomenuté v analýze, implementácia mala zahŕňať RSTP - Rapid Spanning Tree Protocol. Podarilo sa nám dostať k reálnej
implementácií tohto prokotolu v rámci controllera [rstp], ktorý bol vypracovaný v rámci bakalárskej práce. Pri pokuse o spustenie
tohto controllera sme však narazili na problém, kedy nám ani po konvergencií nefungovala sieť. Pri snahe o riešenie sme prišli na 
to, že RSTP je podporované až od verzie OVSswitchu 2.4 a vyššie. Avšak ani update verzie nepomohol správnej funkcionalite celej siete. 

![Nefunkčnosť siete](rstp_err.png)

Nakoniec sme vytvorili Issue [issue] priamo v repozitári tohto projektu. Snažili sme sa spolu vymyslieť, prečo tento protokol
nefunguje. Avšak ani po niekoľkých pokusoch o opravu sa nám nepodarilo správne rozbehnúť tento controller a preto sme sa rozhodli
implementovať RSTP na jednotlivých switchoch, teda manuálne zapnúť tento protokol pomocou príkazu spomenutého v časti Topológie. Aj
napriek tomu, že takáto implementácia nie je tak efektívna ako samotný RSTP v controlleri, z časových dôvodov sme sa rozhodli otestovať
sieť aspoň v takýchto podmienkach. 

# <h1> Záver

# <h2> Zdroje
[rstp] https://github.com/AngeloDamiani/Ryu_RSTP

[issue] https://github.com/AngeloDamiani/Ryu_RSTP/issues/1
