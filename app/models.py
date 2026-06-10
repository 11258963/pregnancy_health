from datetime import datetime
from app import db


class Settings(db.Model):
    """应用设置（预产期等）"""
    __tablename__ = 'settings'

    id = db.Column(db.Integer, primary_key=True)
    due_date = db.Column(db.Date, nullable=False)
    movement_api_token = db.Column(db.String(64))
    movement_reminder_enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WeightRecord(db.Model):
    """孕期体重记录"""
    __tablename__ = 'weight_records'

    id = db.Column(db.Integer, primary_key=True)
    record_date = db.Column(db.Date, nullable=False)
    record_time = db.Column(db.Time)  # 记录时间（从 Apple Health 导入）
    gestational_week = db.Column(db.Integer, nullable=False)
    gestational_day = db.Column(db.Integer, default=0)
    weight = db.Column(db.Float, nullable=False)
    suggested_min = db.Column(db.Float)  # 建议体重下限
    suggested_max = db.Column(db.Float)  # 建议体重上限
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'record_date': self.record_date.isoformat(),
            'record_time': self.record_time.isoformat() if self.record_time else None,
            'gestational_week': self.gestational_week,
            'gestational_day': self.gestational_day,
            'weight': self.weight,
            'suggested_min': self.suggested_min,
            'suggested_max': self.suggested_max
        }

    def calculate_suggested_weight(self, baseline_weight, week=None):
        """计算建议体重范围
        - 孕早期(0-12周): 总增重0-2kg
        - 孕中晚期(13周起): 每周增重0.26-0.48kg
        """
        if week is None:
            week = self.gestational_week

        if week <= 12:
            # 孕早期：0-2kg
            return baseline_weight, baseline_weight + 2.0
        else:
            # 孕中晚期：每周0.26-0.48kg
            weeks_gained = week - 12
            min_gain = 2.0 + (weeks_gained * 0.26)
            max_gain = 2.0 + (weeks_gained * 0.48)
            return baseline_weight + min_gain, baseline_weight + max_gain


class CheckupRecord(db.Model):
    """产检记录"""
    __tablename__ = 'checkup_records'

    id = db.Column(db.Integer, primary_key=True)
    checkup_date = db.Column(db.Date, nullable=False)
    gestational_week = db.Column(db.Integer, nullable=False)
    gestational_day = db.Column(db.Integer, default=0)
    checkup_item = db.Column(db.String(200), nullable=False)
    checkup_item_code = db.Column(db.String(50))
    result = db.Column(db.Text)
    doctor_name = db.Column(db.String(100))
    doctor_notes = db.Column(db.Text)
    next_appointment = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 附件关系
    files = db.relationship('CheckupFile', backref='record', lazy='dynamic', cascade='all, delete-orphan')

    CHECKUP_ITEMS = {
        # 常规检查
        'BP': '血压',
        'WEIGHT': '体重',
        'BLOOD': '血常规',
        'URINE': '尿常规',
        'FUNDUS_HEIGHT': '宫高腹围',
        'FETAL_HEART_RATE': '胎心率',
        'FETAL_POSITION': '胎位',
        'CERVIX_CHECK': '宫颈检查',
        'GYNECOLOGY': '妇科检查',
        'ECG': '心电图',

        # 抽血检查
        'EARLY_TANG': '早期唐筛',
        'MID_TANG': '中期唐筛',
        'NIPT': '无创DNA',
        'OGTT': '糖耐量试验',
        'BILE_ACID': '血清胆汁酸检测',
        'HCG': '血hCG',
        'PROGESTERONE': '血孕酮',
        'HEPATITIS_B': '乙肝筛查',
        'HEPATITIS_C': '丙肝筛查',
        'SYPHILIS': '梅毒筛查',
        'HIV': 'HIV筛查',
        'THALASSEMIA': '地贫筛查',
        'THYROID': '甲功筛查',
        'COAG': '凝血检查',
        'FASTING_BLOOD': '空腹血糖',
        'LIVER': '肝功能',
        'LIVER_KIDNEY': '肾功能',
        'BLOODTYPE': '血型',

        # 超声检查
        'NT': 'NT检查',
        'ULTRASOUND_BIG': 'B超大排畸',
        'ULTRASOUND_SMALL': 'B超小排畸',
        'ULTRASOUND_OB': '产科超声',
        'CERVIX_LENGTH': '测宫颈长度',
        'ULTRASOUND_EARLY': '早孕超声',
        'ULTRASOUND_ROUTINE': '孕中常规彩超',

        # 其他检查
        'FHR': '胎心监护',
        'VILLUS': '绒毛活检',
        'AMNIOCENTESIS': '羊水穿刺',
        'GBS': 'B族链球菌筛查',
        'BUILD_CARD': '建卡',
        'BUILD_RECORD': '建档',

        'OTHER': '其他'
    }

    # 检查项目分组
    CHECKUP_GROUPS = [
        ('常规检查', ['BP', 'WEIGHT', 'BLOOD', 'URINE', 'FUNDUS_HEIGHT', 'FETAL_HEART_RATE', 'FETAL_POSITION', 'CERVIX_CHECK', 'GYNECOLOGY', 'ECG']),
        ('抽血检查', ['EARLY_TANG', 'MID_TANG', 'NIPT', 'OGTT', 'BILE_ACID', 'HCG', 'PROGESTERONE', 'HEPATITIS_B', 'HEPATITIS_C', 'SYPHILIS', 'HIV', 'THALASSEMIA', 'THYROID', 'COAG', 'FASTING_BLOOD', 'LIVER', 'LIVER_KIDNEY', 'BLOODTYPE']),
        ('超声检查', ['NT', 'ULTRASOUND_BIG', 'ULTRASOUND_SMALL', 'ULTRASOUND_OB', 'CERVIX_LENGTH', 'ULTRASOUND_EARLY', 'ULTRASOUND_ROUTINE']),
        ('其他检查', ['FHR', 'VILLUS', 'AMNIOCENTESIS', 'GBS', 'BUILD_CARD', 'BUILD_RECORD', 'OTHER']),
    ]

    # 检查项目简介
    CHECKUP_DESCRIPTIONS = {
        'BP': '每次产检的必查项目。通过监测血压变化，可及时发现妊娠期高血压疾病，预防子痫前期等严重并发症，保障母婴安全。',
        'WEIGHT': '每次产检的必查项目。通过监测体重增长，可评估孕妇营养状况及胎儿发育速度。体重增长过快或过慢，均可能提示潜在问题。',
        'BLOOD': '检查血液中红细胞、白细胞、血小板等指标。主要评估孕妇是否存在贫血、感染或凝血功能异常，是孕期基础且重要的检查。',
        'URINE': '通过检测尿液中的蛋白质、糖分等，筛查妊娠期高血压、妊娠期糖尿病及尿路感染等风险，是监测孕妇健康状况的常规手段。',
        'FUNDUS_HEIGHT': '医生用软尺测量子宫高度和腹部周长。通过数据变化，间接评估胎儿在宫内的生长发育情况，判断其大小是否与孕周相符。',
        'FETAL_HEART_RATE': '使用多普勒胎心仪听取胎儿心跳。正常胎心率是胎儿在宫内状态良好的重要标志，每次产检都会监测，以初步判断胎儿安危。',
        'FETAL_POSITION': '医生通过腹部触诊（四步触诊法）判断胎儿在子宫内的位置，如头位、臀位等。胎位是影响分娩方式的重要因素。',
        'CERVIX_CHECK': '在孕晚期，医生通过内检评估宫颈的软硬度、消退和扩张程度，以判断分娩发动的临近程度和产程进展。',
        'GYNECOLOGY': '孕早期进行的检查，通过窥器和双合诊，了解生殖道有无炎症、畸形或肿瘤，评估子宫大小是否与停经周数相符。',
        'ECG': '孕早期常规检查。评估孕妇的心脏功能，排查心律失常、心肌缺血等问题，确保心脏能承受孕期增加的负担。',
        'EARLY_TANG': '孕11-13周+6天进行。结合B超NT值和孕妇血清指标，评估胎儿患唐氏综合征等染色体异常的风险，属于早期筛查。',
        'MID_TANG': '孕15-20周进行。通过抽取孕妇静脉血，检测血清中的特定生化指标，结合孕周、年龄等，评估胎儿患唐氏综合征的风险。',
        'NIPT': '孕12周后可进行。通过采集孕妇外周血，提取胎儿游离DNA进行测序，筛查21-三体、18-三体等常见染色体非整倍体疾病，准确率高。',
        'OGTT': '孕24-28周进行。通过空腹及口服葡萄糖后不同时间点的血糖值，诊断孕妇是否患有妊娠期糖尿病，以便及时干预。',
        'BILE_ACID': '当孕妇出现皮肤瘙痒时，需进行此项检查。血清总胆汁酸升高是诊断妊娠期肝内胆汁淤积症的关键指标，该病对胎儿有风险。',
        'HCG': '人绒毛膜促性腺激素。孕早期通过监测其翻倍情况，可辅助判断胚胎发育是否良好，以及排查宫外孕、先兆流产等。',
        'PROGESTERONE': '孕早期检查项目。孕酮是维持妊娠的重要激素，其水平过低可能提示黄体功能不足或胚胎发育不良，有流产风险。',
        'HEPATITIS_B': '孕早期必查项目。筛查孕妇是否感染乙型肝炎病毒。若为阳性，新生儿出生后需立即注射乙肝免疫球蛋白和疫苗，以阻断母婴传播。',
        'HEPATITIS_C': '孕早期必查项目。筛查孕妇是否感染丙型肝炎病毒。目前虽无疫苗预防，但明确感染状态有助于在分娩时采取相应措施，减少传播风险。',
        'SYPHILIS': '孕早期必查项目。筛查孕妇是否感染梅毒。若确诊，孕期进行规范的青霉素治疗，可有效预防胎儿感染，避免发生先天性梅毒。',
        'HIV': '孕早期必查项目。筛查孕妇是否感染艾滋病病毒。及早发现并进行抗病毒治疗，可极大降低母婴传播的风险，保障婴儿健康。',
        'THALASSEMIA': '地中海贫血筛查。通过血常规和血红蛋白电泳等，筛查夫妻双方是否携带地中海贫血基因。若双方均为同型携带者，胎儿有患病风险。',
        'THYROID': '甲状腺功能筛查。甲状腺激素对胎儿神经系统发育至关重要。筛查可及时发现孕妇甲状腺功能亢进或减退，并进行干预。',
        'COAG': '评估孕妇的凝血功能。孕期血液处于高凝状态，此项检查可排查凝血功能障碍，为预防产后大出血及血栓形成提供依据。',
        'FASTING_BLOOD': '孕早期检查项目。用于评估孕妇的基础血糖水平，是早期发现孕前糖尿病或血糖异常的重要指标。',
        'LIVER': '评估肝脏的代谢和解毒功能。孕期肝脏负担加重，此项检查可及时发现妊娠期肝损伤或妊娠期急性脂肪肝等严重并发症。',
        'LIVER_KIDNEY': '评估肾脏的滤过和排泄功能。孕期肾脏负担增加，此项检查有助于及早发现妊娠期高血压疾病对肾脏造成的损害。',
        'BLOODTYPE': '孕早期必查项目。明确孕妇ABO血型和Rh血型。若为Rh阴性血（熊猫血），需特别监护，预防新生儿溶血病的发生。',
        'NT': '孕11-13周+6天进行。通过B超测量胎儿颈项透明层厚度，是孕早期筛查胎儿染色体异常（如唐氏综合征）的重要指标。',
        'ULTRASOUND_BIG': '孕20-24周进行。系统筛查胎儿头颅、脊柱、心脏、腹部脏器等主要结构，旨在发现严重的胎儿结构畸形，是孕期最重要的超声检查之一。',
        'ULTRASOUND_SMALL': '孕28-32周进行。作为大排畸的补充，主要观察孕晚期才显现或变化的胎儿结构，并评估胎儿生长发育、羊水及胎盘情况。',
        'ULTRASOUND_OB': '泛指孕期所有用于评估胎儿和母体状况的超声检查。包括确认宫内妊娠、监测胎儿生长、评估羊水胎盘、确定胎位等。',
        'CERVIX_LENGTH': '通过经阴道或腹部B超测量宫颈管长度。宫颈过短是早产的高危因素，此项检查主要用于有早产风险的孕妇，以便及时干预。',
        'ULTRASOUND_EARLY': '孕6-8周进行。主要目的是确认是否为宫内妊娠、观察孕囊、胎芽和原始心管搏动，以排除宫外孕并判断胚胎是否存活。',
        'ULTRASOUND_ROUTINE': '孕中期进行的常规超声检查。主要测量胎儿双顶径、股骨长等生长指标，评估胎儿大小、羊水量和胎盘位置，了解发育是否达标。',
        'FHR': '孕32周后开始。通过胎心监护仪连续记录胎心率、胎动和宫缩情况，评估胎儿在宫内的储备能力和有无缺氧迹象。',
        'VILLUS': '孕11-14周进行。在B超引导下，经宫颈或腹部获取少量胎盘绒毛组织进行染色体分析，属于有创的产前诊断方法。',
        'AMNIOCENTESIS': '孕16-22周进行。在B超引导下，抽取少量羊水，获取胎儿脱落细胞进行染色体核型分析，是诊断胎儿染色体疾病的"金标准"。',
        'GBS': '孕35-37周进行。通过采集阴道和直肠拭子，筛查是否携带B族链球菌。若为阳性，分娩时需使用抗生素，预防新生儿感染。',
        'BUILD_CARD': '即建立《孕产妇保健手册》。通常在孕12周左右，在居住地社区卫生服务中心进行，记录孕妇基本信息和历次产检结果，是孕期管理的起点。',
        'BUILD_RECORD': '在计划分娩的医院建立产科病历。一般在孕12-16周完成，意味着确定了分娩医院，后续的重要产检和分娩都将在此医院进行。',
        'OTHER': '其他检查项目。',
    }

    def to_dict(self):
        return {
            'id': self.id,
            'checkup_date': self.checkup_date.isoformat(),
            'gestational_week': self.gestational_week,
            'checkup_item': self.checkup_item,
            'checkup_item_code': self.checkup_item_code,
            'result': self.result,
            'doctor_name': self.doctor_name,
            'doctor_notes': self.doctor_notes,
            'next_appointment': self.next_appointment.isoformat() if self.next_appointment else None
        }


class CheckupFile(db.Model):
    """检查记录附件"""
    __tablename__ = 'checkup_files'

    id = db.Column(db.Integer, primary_key=True)
    checkup_record_id = db.Column(db.Integer, db.ForeignKey('checkup_records.id', ondelete='CASCADE'), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(20), nullable=False)  # 'image' or 'document'
    mime_type = db.Column(db.String(100))
    file_size = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'original_filename': self.original_filename,
            'file_type': self.file_type,
            'mime_type': self.mime_type,
            'file_size': self.file_size,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class MovementSession(db.Model):
    """胎动计数会话（每天可多次尝试，仅一条达标记录）"""
    __tablename__ = 'movement_sessions'

    id = db.Column(db.Integer, primary_key=True)
    session_date = db.Column(db.Date, nullable=False, index=True)
    gestational_week = db.Column(db.Integer, nullable=False)
    gestational_day = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), nullable=False, default='in_progress')
    is_qualified = db.Column(db.Boolean, default=False)
    started_at = db.Column(db.DateTime)
    ended_at = db.Column(db.DateTime)
    kick_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    kicks = db.relationship(
        'MovementKick',
        backref='session',
        lazy='dynamic',
        cascade='all, delete-orphan',
        order_by='MovementKick.sequence'
    )

    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_ABANDONED = 'abandoned'

    def deadline_at(self):
        if not self.started_at:
            return None
        from datetime import timedelta
        return self.started_at + timedelta(seconds=7200)

    def duration_seconds(self):
        if not self.started_at:
            return None
        end = self.ended_at or datetime.now()
        return int((end - self.started_at).total_seconds())

    def to_dict(self):
        kicks = self.kicks.order_by('sequence').all()
        return {
            'id': self.id,
            'session_date': self.session_date.isoformat(),
            'gestational_week': self.gestational_week,
            'gestational_day': self.gestational_day,
            'status': self.status,
            'is_qualified': self.is_qualified,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'ended_at': self.ended_at.isoformat() if self.ended_at else None,
            'kick_count': self.kick_count,
            'deadline_at': self.deadline_at().isoformat() if self.deadline_at() else None,
            'duration_seconds': self.duration_seconds(),
            'kicks': [k.to_dict() for k in kicks],
        }


class MovementKick(db.Model):
    """单次胎动点击"""
    __tablename__ = 'movement_kicks'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(
        db.Integer,
        db.ForeignKey('movement_sessions.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    kicked_at = db.Column(db.DateTime, nullable=False)
    sequence = db.Column(db.Integer, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'kicked_at': self.kicked_at.isoformat(),
            'sequence': self.sequence,
        }


class FetalRecord(db.Model):
    """胎心胎动记录"""
    __tablename__ = 'fetal_records'

    id = db.Column(db.Integer, primary_key=True)
    record_date = db.Column(db.DateTime, nullable=False)
    gestational_week = db.Column(db.Integer, nullable=False)
    record_type = db.Column(db.String(20), nullable=False)  # manual/timer
    fetal_heart_rate = db.Column(db.Integer)
    movement_count = db.Column(db.Integer)
    movement_duration = db.Column(db.Integer)  # 秒
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'record_date': self.record_date.isoformat(),
            'gestational_week': self.gestational_week,
            'record_type': self.record_type,
            'fetal_heart_rate': self.fetal_heart_rate,
            'movement_count': self.movement_count,
            'movement_duration': self.movement_duration,
            'notes': self.notes
        }
