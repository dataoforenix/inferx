// Arabic names for the machinery and raw materials in backend/data/categories.csv, which lists them in
// English only. Unknown terms are shown as they come. `null` hides a fragment: older data split the potatoes
// entry in two (a ";" inside its parentheses), so its second half is folded into the first.
const AR = {
  'Aseptic or can filler': 'ماكينة تعبئة معقّمة أو تعبئة علب',
  'Assembly line': 'خط تجميع',
  'Balancing machine': 'ماكينة موازنة',
  'Blade press or moulding': 'مكبس أو قالب للشفرات',
  Blancher: 'جهاز سلق بالبخار',
  Bolts: 'براغي',
  'CNC/hydraulic tube bender': 'ماكينة ثني أنابيب CNC أو هيدروليكية',
  'Cans or jars': 'علب أو مرطبانات',
  'Capacitors and switches': 'مكثفات ومفاتيح كهربائية',
  Chiller: 'مبرّد صناعي (تشيلر)',
  'Coil winding machines': 'ماكينات لف الملفات',
  'Cold store': 'غرفة تبريد',
  'Cold-rolled steel coil': 'لفائف صاج مدرفل على البارد',
  'Electric motors (imported)': 'محركات كهربائية (مستوردة)',
  'Electrical safety test bench': 'منصة فحص السلامة الكهربائية',
  'Fabric or PU leather': 'قماش أو جلد صناعي',
  Fasteners: 'براغي وصواميل التثبيت',
  Foam: 'إسفنج',
  'Fresh tomatoes (grown in Jordan)': 'بندورة طازجة (مزروعة في الأردن)',
  'Frying oil': 'زيت قلي',
  'Galvanised steel sheet': 'صاج مجلفن',
  Granulator: 'كسّارة بلاستيك',
  'Hot-break unit': 'وحدة تسخين أولي للعصير',
  'IQF tunnel freezer': 'نفق تجميد سريع',
  'Industrial sewing machines': 'ماكينات خياطة صناعية',
  'Injection moulding machine 150-250 t': 'ماكينة حقن بلاستيك (150 إلى 250 طن)',
  'MIG welders': 'ماكينات لحام MIG',
  'Masterbatch colour': 'ملوّنات بلاستيك (ماستر باتش)',
  'Packaging film': 'أفلام تغليف',
  'Packing machine': 'ماكينة تعبئة وتغليف',
  'Packing table': 'طاولة تعبئة',
  'Par-fryer': 'قلّاية قلي أولي',
  'Plastic parts': 'قطع بلاستيكية',
  'Polypropylene granules': 'حبيبات بولي بروبيلين',
  'Polystyrene granules': 'حبيبات بوليسترين',
  'Potatoes (grown in Jordan from imported seed potatoes)': 'بطاطا (مزروعة في الأردن من بذور مستوردة)',
  'Potatoes (grown in Jordan': 'بطاطا (مزروعة في الأردن من بذور مستوردة)',
  'seed potatoes imported)': null,
  'Powder paint': 'دهان بودرة',
  'Powder-coating booth and oven': 'كابينة وفرن دهان بودرة',
  'Powder-coating line': 'خط دهان بودرة',
  'Press brake': 'ثنّاية صاج',
  'Pulper/finisher': 'ماكينة هرس وتصفية',
  'Punching press': 'مكبس تخريم',
  'Roll-forming line (uprights)': 'خط تشكيل بالدرفلة للقوائم',
  Salt: 'ملح',
  'Sheet shear': 'مقص صاج',
  'Spot/MIG welding': 'لحام نقطي أو MIG',
  'Steel moulds': 'قوالب فولاذية',
  'Steel sheet': 'صاج فولاذي',
  'Steel tube': 'أنابيب فولاذية',
  'Strip cutter': 'ماكينة تقطيع أصابع',
  'Tube cutting saw': 'منشار قص أنابيب',
  'Upholstery table': 'طاولة تنجيد',
  'Vacuum evaporator': 'مبخّر تحت التفريغ',
  'Washer and peeler': 'ماكينة غسيل وتقشير',
  'Washer and sorter': 'ماكينة غسيل وفرز',
};

/** Arabic name of a CSV term, the term itself when unknown, or null for a fragment to hide. */
export function termAr(term) {
  const key = term.trim();
  return key in AR ? AR[key] : key;
}

/** Arabic names for a list of CSV terms, with hidden fragments dropped. */
export const termsAr = (list = []) => list.map(termAr).filter(Boolean);
