"""Constants for the Parcel integration."""

DOMAIN = "parcelapp"
PARCEL_URL = "https://api.parcel.app/external/deliveries/"
UPDATE_INTERVAL_SECONDS = 300  # RATE LIMIT IS 20 PER HOUR
DELIVERY_STATUS_CODES = {
    0:"Completed delivery.",
    1:"Frozen delivery. There were no updates for a long time or something else makes the app believe that it will never be updated in the future.",
    2:"Delivery in transit.",
    3:"Delivery expecting a pickup by the recipient.",
    4:"Out for delivery.",
    5:"Delivery not found.",
    6:"Failed delivery attempt.",
    7:"Delivery exception, something is wrong and requires your attention.",
    8:"Carrier has received information about a package, but has not physically received it yet."
    }
RETURN_CODES = {
    -1: "No active parcels.",
    -2: "Active parcel(s) but no ETA.",
    -3: "Error"
}
class Shipment():
    """Representation of a shipment as per the ParcelApp API."""
    def __init__(self,
        carrier_code = "carrier_code",
        description = "description",
        status_code = 5,
        tracking_number = "tracking_number",
        extra_information = None,
        date_expected = None,
        date_expected_end = None,
        timestamp_expected = None,
        timestamp_expected_end = None,
        events = []
        ):
        self.carrier_code = carrier_code
        self.description = description
        self.status_code = status_code
        self.tracking_number = tracking_number
        self.extra_information = extra_information
        self.date_expected = date_expected
        self.date_expected_end = date_expected_end
        self.timestamp_expected = timestamp_expected
        self.timestamp_expected_end = timestamp_expected_end
        self.events = events
# From https://api.parcel.app/external/supported_carriers.json
CARRIER_CODES = {
    "abf":"ABF Freight","acs":"ACS Courier","adrexo":"Colis Privé","airroad":"AirRoad","aliex":"AliExpress Shipping (Cainiao)","allegro":"Allegro One","allied":"Allied Express","amshipfr":"Amazon Shipping France","amshipit":"Amazon Shipping Italy","amshipuk":"Amazon Shipping UK","amzlae":"Amazon UAE","amzlau":"Amazon Australia","amzlbe":"Amazon Belgium","amzlbr":"Amazon Brazil","amzlca":"Amazon Canada","amzlde":"Amazon Germany","amzleg":"Amazon Egypt","amzles":"Amazon Spain","amzlfr":"Amazon France","amzlin":"Amazon India","amzlit":"Amazon Italy","amzljp":"Amazon Japan","amzlmx":"Amazon Mexico","amzlnl":"Amazon Netherlands","amzlpl":"Amazon Poland","amzlsa":"Amazon Saudi Arabia","amzlse":"Amazon Sweden","amzlsg":"Amazon Singapore","amzltr":"Amazon Turkey","amzluk":"Amazon UK","amzlus":"Amazon US","anc":"ANC Delivers","anpost":"Anpost","apc":"APC Overnight","apcpli":"APC-PLI","apex":"Apex","apge":"APG eCommerce","apple":"Apple Store Orders","appleexp":"Apple Express","aquiline":"Aquiline","aramex":"Aramex","arrowxl":"Arrow XL","asendia":"Asendia USA","asendiag":"Asendia","asmred":"GLS Spain","at":"Austrian Post","au":"Australia Post","azer":"Azerpost","bartol":"Bartolini","bettert":"Better Trucks","blp":"Belpost","bluecare":"Bluecare Express","bluedart":"Blue Dart","bolg":"Bulgarian Post","bonshaw":"Postmedia Parcel Services","boxb":"Boxberry","bpost":"Bpost","bring":"Bring","buylogic":"Buylogic","canpar":"Canpar","cdl":"CDL Last Mile","cems":"China Post EMS","ceska":"Česká pošta","ceva":"Ceva Logistics","chilex":"Chilexpress","china":"China Post","chitchats":"Chit Chats","chrexp":"Correos Express","chrono":"Chronopost","chronop":"Chronopost Portugal","cirro":"Cirro","cjpacket":"CJPacket","cneexp":"CNE Express","colicoli":"Colicoli","colomb":"Colombia post (4-72)","colp":"Collect+","cope":"COPE","cor":"Correos","corbra":"Correios","corm":"Correos de Mexico","corurg":"Correo Uruguayo","coup":"CourierPost","couple":"Couriers Please","cp":"Canada Post","cse":"CSE","ctt":"CTT","cyclpcode":"Cycloon","cypr":"Cyprus Post","dachser":"Dachser","dao365":"DAO365","deliverit":"Deliver-it","dellin":"Delovie Linii","delmas":"Delmas","dhl":"DHL Express","dhlgf":"DHL Global Forwarding","dhlgm":"DHL Global Mail","dhlnl":"DHL Netherlands","dhlpoland":"DHL Poland","dhlsc":"DHL Supply Chain","dhlserv":"DHL Servicepoint","dhluk":"DHL Parcel UK","dicom":"GLS Canada","dimex":"Dimex","direct":"Direct Link","dk":"Post Danmark","dp":"Deutsche Post","dpd":"DPD Germany","dpdat":"DPD Austria","dpdgroup":"DPD Group","dpdie":"DPD Ireland","dpdpoland":"DPD Poland","dpduk":"DPD UK","dpexw":"DPEX Worldwide","dpr":"Deutsche Post Brief","dragonfly":"Dragonfly","dsv":"DSV","dtdc":"DTDC India","dx":"DX","dynalogic":"Dynalogic","dynamex":"Dynamex","easyship":"Easyship","ecms":"ECMS","econt":"Econt Express","ecoscoot":"EcoScooting","edos":"CDEK","ee":"Eesti Post","elta":"Elta","emirates":"Emirates Post","emps":"Emps","ems":"EMS Russian Post","energia":"TK Energia","envia":"Ontime - Envialia","eshopw":"eShopWorld","estafe":"Estafeta","ets":"ETS Express","exa":"Exapaq","fastau":"Fastway AU","fasthorse":"Fast Horse Express","fastie":"Fastway Ireland","fastnz":"Fastway NZ","fedex":"FedEx","fedpl":"FedEx Poland","fivepost":"5post","fleetpcode":"FleetOptics","gelpcode":"GEL Express","geniki":"Geniki Taxydromiki","geodis":"Geodis","globalp":"GlobalPost","gls":"GLS","glsit":"GLS Italy","gobolt":"GoBolt","gofo":"GOFO Express","gover":"General-Overnight","gso":"GLS US","hawai":"Hawaiian Air Cargo","her2mann":"Hermes 2-Mann-Handling","hermes":"Hermes","hk":"Hongkong Post","homerr":"Homerr","hr":"Hrvatska pošta","hr2":"Hrvatska pošta (int.)","hrpar":"HR Parcel","hung":"Magyar Posta","ics":"ICS Courier","il":"Israel Post","iloxx":"iloxx","imile":"iMile","imx":"IMX France","in":"India Post","indon":"Indonesia Post","inpespcode":"Inpost Spain","inpost":"InPost Paczkomaty","inpostit":"InPost Italy","inpostuk":"InPost UK","intelc":"Dragonfly - Intelcom","inter":"Interlink","ipar":"i-parcel","it":"Poste Italiane","jadlog":"JadLog","jde":"JDE","jnet":"J-NET","joeyco":"JoeyCo","jordan":"Jordan Post","jp":"Japan Post","keavo":"Keavo","kerry":"Kerry Express","kor":"Korea Post","koreanair":"Korean Air Cargo","kz":"Kazpost","landmark":"Landmark Global","laser":"OnTrac - Lasership","litva":"Lietuvos paštas","litva2":"LP Express","loggi":"Loggi","loom":"Loomis Express","lp":"La poste (Colissimo)","lp2":"La Poste (Courrier Suivi)","lso":"Lone Star Overnight","lv":"Latvijas Pasts","major":"Major Express","malpos":"Malaysia Post","malta":"MaltaPost","matka":"Matkahuolto","meest":"Meest","mengtu":"Mengtu","moldov":"Moldova Post","mrw":"MRW","mscgva":"MSC","myher":"Evri","nacex":"Nacex","naqel":"Naqel Express","nationex":"Nationex","newp":"Nova Poshta","nor":"Norway Post","northline":"Northline","nzp":"New Zealand Post","oca":"OCA Argentina","ocs":"OCS Worldwide","ont":"OnTrac","optima":"Optima","p2g":"Parcel2Go","p4d":"P4D","paack":"Paack","packeta":"Packeta","paczka":"OrlenPaczka","pandion":"Pandion","paquet":"Paquetexpress","parcelpnt":"ParcelPoint","passport":"Passport Shipping","pbi":"PBI - Pitney Bowes","pbt":"PBT New Zealand","pec":"PEC","pfl":"Parcel Freight Logistics","phlpost":"Philpost","pilot":"Pilot Freight","pk":"Pakistan Post","planzer":"Planzer","poland":"Poczta Polska","posthas":"Post Haste","posti":"Posti Finland - Itella","postnord":"Postnord Logistics","ppl":"PPL","ppx":"PPX (RR Donnelley)","prfc":"Parcelforce","ptl":"P&T Luxembourg","puro":"Purolator","puropost":"PuroPost","px":"4PX","quickpac":"Quickpac","qxpress":"Qxpress","raven":"Raven Force Couriers","redjep":"Instabox Red je pakketje","redpack":"Redpack","relais":"Relais Colis","relay":"Mondial Relay","rm":"Royal Mail","roadie":"Roadie","rp":"Russian Post","safmar":"Safmarine","safr":"South African Post Office","sagawa":"Sagawa Express","saudi":"Saudi Post","sch":"DB Schenker","schen":"DB Schenker Sweden","se":"Swedish Post","seabour":"Seabourne Logistics","sendle":"Sendle","serbia":"Serbia Post","serpost":"Serpost","seur":"SEUR","sf":"SF Express","sfc":"SendFromChina","shiptor":"Shiptor","sing":"SingPost","skynetm":"Skynet Malaysia","skynetw":"SkyNet Worldwide Express","slovak":"Slovenská pošta","slv":"Pošta Slovenije","smsa":"SMSA Express","speedpak":"SpeedPAK","speedx":"SpeedX","sprintstar":"Sprintstar","star":"StarTrack Express","straight":"Straightship","swiship":"Swiship","swiss":"Swiss Post","syncreon":"Syncreon","sypost":"Sypost - SunYou Logistics","thai":"Thailand Post","tipsac":"Tipsa","tkkit":"TK KIT","tnt":"TNT","tntau":"TNT Australia","tntfr":"TNT France","tntit":"TNT Italy","tntp":"PostNL","tntpit":"PostNL (International)","tntuk":"TNT UK","toll":"Toll - Team Global Express","topyou":"TopYou Logistics","tourline":"CTT Express","transm":"TransMission","trpack":"TrakPak","turk":"PTT","tw":"Taiwan (Chunghwa) Post","ubi":"UBI Smart Parcel","udsa":"UDS - United Delivery Service","ukr":"Ukrpost","unex":"Unex","uniuni":"UniUni","ups":"UPS","upsmi":"UPS MI","usps":"USPS","vasp":"Vasp Expresso","vietnam2":"Vietnam Post EMS","vinted":"Vinted Go","whistl":"Whistl","winit":"Winit","wish":"Wish Post","wnd":"wnDirect","xdp":"XDP","yamato":"Yamato","yanwen":"Yanwen","yodel":"Yodel","yun":"Yun Express","zel":"Zeleris"
}