# ai_processor.py
from openai import OpenAI
import json
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential
from models import Article, RatingResult
from config import config
from AIScenarioManager import ScenarioManager


class AIProcessor:
    def __init__(self, config: config, logger):
        self.config = config
        self.logger = logger
        #self.client = openai.OpenAI(api_key=config.OPENAI_API_KEY)
        self.client = OpenAI()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def rate_article(self, article: Article) -> Optional[RatingResult]:
        """Rate article for Russian audience interest and lurk-style translatability"""

        prompt = f"""
        Проанализируй следующую новость на английском языке и верни оценки в формате JSON:

        Заголовок: {article.title}
        Краткое содержание: {article.summary}
        Теги: {article.tags or 'нет'}

        Нужно оценить по четырем критериям:
        1. interest_score (0-100): Насколько эта новость будет интересна русскоязычной аудитории, интересующейся кино, ТВ, развлечениями
        2. lurkable_score (0-100): Насколько хорошо эту новость можно пересказать в стиле lurkmore.ru (ироничный, саркастичный, с мемами и сленгом)
        3. rhymable_score (0-100): Насколько хорошо эту новость можно пересказать в рифме в стиле русского авангарда
        4. Category: Выбери код категории новости:
            A - movie_industry - Всё, что связано с производством, релизами, деньгами, бизнесом и внутренней кухней индустрии
            B - rumor - Неофициальные утечки сценариев, сцен, сюжета; неподтверждённые слухи о фильмах или актёрах; сплетни
            C - scandal - Скандалы, отмены, общественное возмущение, раскрытие сексуальной ориентации или гендерной идентичности, личные трагедии и переживания
            D - abuse - Насилие, домогательства, ненадлежащее поведение
            E - public_image - Когда меняется публичный образ: активизм, конфликты, возвращения, культурные дебаты
            F - award - Номинации и получение наград
            G - health - Госпитализация, болезни, травмы, смерть, некрологи
            P - popuri - В одной новости смешано несколько несвязанных новостей
            Z - other - Все остальные категории

        Учти:
        - Русская аудитория интересуется только теми голливудским кино, сериалами, знаменитостями, которые стали популярны в России
        - Lurk-стиль: ироничный, саркастичный, с использованием интернет-сленга и мемов
        - для категорий P, G, Z выставь interest_score = 10, lurkable_score = 10

        Верни ТОЛЬКО JSON в формате:
        {{
            "interest_score": <число 0-100>,
            "lurkable_score": <число 0-100>,
            "rhymable_score": <число 0-100>,
            "reasoning": "<краткое объяснение оценок>",
            "category": "<категория>"
        }}
        
        Пример ответа:
        {{
            "interest_score": 75,
            "lurkable_score": 60,
            "rhymable_score": 80,
            "reasoning": "Русскоязычная аудитория, интересующаяся кино и развлечениями, вероятно, заинтересуется новыми подходами Джеймса Ганна к известному персонажу",
            "category": "A"            
        }}
        """

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system",
                     "content": "Ты эксперт по медиа-контенту и интернет-культуре. Отвечай только в JSON формате."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.1
            )

            result_text = response.choices[0].message.content.strip()

            # Parse JSON response
            try:
                result_data = json.loads(result_text)
                return RatingResult(
                    interest_score=result_data['interest_score'],
                    lurkable_score=result_data['lurkable_score'],
                    reasoning=result_data.get('reasoning', ''),
                    category=result_data['category'],
                )
            except json.JSONDecodeError:
                self.logger.error(f"Failed to parse JSON response: {result_text}")
                return None

        except Exception as e:
            self.logger.error(f"Error rating article {article.id}: {str(e)}")
            return None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def translate_to_lurk(self, article: Article, full_content: str = None) -> Optional[str]:
        """Translate article to lurk-style Russian"""

        content_to_translate = full_content or article.summary
        self.logger.info(f"article's category {article.category}")
        #-------


        scenario_manager = ScenarioManager()
        #scenario = scenario_manager.get_random_scenario(article.category)
        scenario = scenario_manager.get_random_scenario(article.category, article.rhymable)

        prompt_user = f"""
            Перескажи следующую новость:
            {article.title}
            {content_to_translate}
            Пример ответа:
            {scenario['example']}
        """

        prompt_sys = f"""
            Твоя задача - пересказать новость на русском языке в саркастичной, едкой, ироничной манере с долей черного юмора. 
            {scenario['txt1']}
            Ты получишь английский текст новости относящей к миру кино. Имей ввиду, что текст получен веб-парсингом и может содержать нерелевантные артефакты
            
            Выполни пошаговый анализ текста:
            Шаг 1. Определи, как эта новость может заинтересовать русскоговорящую аудиторию. Запомни ответ
            Шаг 2. Определи основную идею текста. Запомни ответ
            Шаг 3. На основе ответов шагов 1 и 2 напиши на русском короткий "прожаривающий" пересказ текста в точности следуя правилам и придерживаясь рекомендаций ниже:   
            
            Правила и ограничения:
            - выходной текст ограничен 950 символами
            - используй ответы шагов 1 и 2
            - текст должен быть грамматически корректен. Обращай внимание на согласование окончаний слов, а имена собственные оставляй на языке оригинала
            - на выходе должен быть только текст пересказа
            - для формитирования допустимы только html тэги <b>, <i>, <u>
            - придерживайся следующей структуры выходного текста:
                * <b>заговок</b>, с эмодзи в начале
                * основная мысль новости
                * экспозиция или история, чтобы объяснить мотивацию персонажей
                * остальная часть новости
                * punchline с эмодзи (🎯🤡😏🧠😂) 
            - в тексте допустимо 3-5 эмодзи
            - начинать лучше со структуры "Персонаж сделал то-то". Избегать вводных слов "Итак, Так вот, ..."
            - лучше не использовать слово капитализм, а заменять его на синонимы и метафоры
            - нельзя придумывать факты
                
            Рекомендации к стилю:
            {scenario['txt2']}
        """
        #и вопросом к читателю

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o", #-mini
                messages=[
                    {"role": "system",
                     "content": prompt_sys},
                    {"role": "user", "content": prompt_user}
                ],
                max_tokens=1000,
                temperature=0.7
            )
            self.logger.error("Main AI request done")

            fin_output = response.choices[0].message.content.strip()
            self.logger.info(f"Main AI request - {fin_output}")
            #проверочный промпт
            prompt_sys = "Переводи в стиле lurkmore.ru: ироничный, саркастичный тон с мемами и интернет-сленгом, но сохраняя точность и информативность."
            prompt_user = f"""
                Тебе на вход будет дан текст на русском языке с названиями на языке оригинала
                В тексте могут встречаться ошибки
                Твоя задача проверить корректность написания входного текста на русском языке
                Текст должен быть грамматически корректен, особенно в части окончаний
                При обнаружении ошибки необходимо скорректировать текст полностью сохраняя стилистику и смысл текста
                Если ошибок не найдено, верни текст без изменений
                Входной текст - {fin_output}
            """
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": prompt_sys},
                    {"role": "user", "content": prompt_user}
                ],
                max_tokens=1000,
                temperature=0.7
            )
            fin_output = response.choices[0].message.content.strip()
            self.logger.info(f"Errors check - {fin_output}")
            self.logger.info("Errors check done")

            if len(fin_output) > 1024:
                prompt_user = f"""
                    Condense the following text to under 1000 characters while preserving its original meaning, tone, and style.
    
                    Text to optimize:
                    {fin_output}
    
                    Requirements:
                    - Maximum 1000 characters
                    - Maintain key information and main points
                    - Preserve writing style and voice
                    - Ensure clarity and readability
                """
                prompt_sys = "Переводи в стиле lurkmore.ru: ироничный, саркастичный тон с мемами и интернет-сленгом, но сохраняя точность и информативность."

                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system",
                         "content": prompt_sys},
                        {"role": "user", "content": prompt_user}
                    ],
                    max_tokens=1000,
                    temperature=0.7
                )
                fin_output = response.choices[0].message.content.strip()
                self.logger.error("Aux AI shortening request done")


            return fin_output

        except Exception as e:
            self.logger.error(f"Error translating article {article.id}: {str(e)}")
            return None


def dummy():
        pass
        #------------------prompt backup    translate_to_lurk
        '''
        prompt_old = f"""
            Переведи следующую новость с английского на русский язык в стиле lurkmore.ru:
    
            Заголовок: {article.title}
            Содержание: {content_to_translate}
            
            Требования к переводу:
            1. Используй ироничный, саркастичный тон lurk.com
            2. Добавь интернет-сленг и мемы где уместно
            3. Сохрани все факты, но подай их с иронией
            4. Используй современный русский интернет-сленг
            5. Добавь комментарии в скобках, если нужно объяснить контекст
            6. Сделай текст живым и интересным для чтения
    
            Структура ответа:
            - Сначала цепляющий заголовок
            - Затем основной текст с подробностями
            - В конце можно добавить ироничный комментарий
    
            Не используй чрезмерно грубые выражения, но сохрани живость и остроту стиля.
        """

        prompt_old = f"""
            Переведи следующую новость с английского на русский язык в стиле <b>lurkmore.ru</b> — ироничной, саркастичной и псевдо-энциклопедической «википедии». Стиль должен быть узнаваемо интернетно-мемным, но без чрезмерной пошлости.
    
            🎯 Требования:
            - Используй <b>сарказм, мемы, интернет-сленг</b>, но так, чтобы оригинальные факты сохранялись.
            - Добавляй <b>ироничные врезки в скобках</b> — с пояснениями или личными комментариями в духе "лол", "ну да, конечно".
            - Можешь использовать <b>звёздочки и заглавные буквы</b> для имитации стилистики форума или энциклопедии Lurk.
            - Подражай формату: <b>цепляющий заголовок</b>, затем разбор <b>в вольной форме</b>, в конце — <b>саркастичный вывод или мораль</b>.
            - Ответ должен быть грамматически корректен на русском. В том числе следи за корректностью согласования окончаний.
            - Для форматирования текста можно использовать только тэги из списка - <b>, <i>, <u>, <blockquote>. Иные тэги и Markdown недопустимы
            - Ответ должен начинаться с заголовка, заключенного в <b>-тэг. Слово Заголовок не нужно использовать
            
            Ограничение:
            - Ответ должен быть кратким не более 1400 символов
            
            Исходная статья:
            Заголовок - {article.title}
            Текст статьи - {content_to_translate}
    
            Сделай так, чтобы читатель ржал и пересылал друзьям.
        """

        prompt_old = f"""
            Переведи следующую новость с английского на русский язык в стиле <b>lurkmore.ru</b> — ироничной, саркастичной и псевдо-энциклопедической «википедии».
    
            🎯 Правила:
            - Используй <b>сарказм, мемы, интернет-сленг</b>, но сохраняй факты.
            - Добавляй <b>ироничные комментарии в скобках</b>, но не увлекайся.
            - Можно использовать <b>звёздочки, ЗАГЛАВНЫЕ СЛОВА</b>, как на форумах.
            - Структура: <b>цепляющий заголовок</b>, короткий <b>вольный пересказ</b>, <b>саркастичная мораль</b>.
            - Только тэги: <b>, <i>, <u>, <blockquote>.
            - Начни с заголовка, обёрнутого в <b> (без слова "Заголовок").
            - Ответ должен быть грамматически корректен.
            - <b>Жёсткое ограничение: не более 1000 символов!</b> Урежь детали, если нужно.
    
            Исходная статья:
            Заголовок — {article.title}
            Текст — {content_to_translate}
    
            Сделай так, чтобы читатель ржал и пересылал друзьям.
        """

        prompt_old = f"""
            Translate the following news article from English to Russian in the style of <b>lurkmore.ru</b> — an ironic, sarcastic, and pseudo-encyclopedic “Wikipedia”.
            
            🎯 Rules:
            - Use <b>sarcasm, memes, and internet slang</b>, but keep the facts.
            - Add <b>ironic comments in parentheses</b>, but don’t overdo it.
            - You may use <b>asterisks and ALL CAPS</b>, like on forums.
            - Structure: <b>catchy headline</b>, short <b>freeform retelling</b>, <b>sarcastic moral</b>.
            - Only allowed tags: <b>, <i>, <u>, <blockquote>.
            - Start with the title wrapped in <b> (do NOT include the word “Title”).
            - The response must be grammatically correct.
            - <b>Output hard limit: no more than 1000 characters including all tags!</b> Trim details if needed.
            
            Original article:
            Title — {article.title}
            Text — {content_to_translate}
            
            Make it so funny the reader wants to forward it to their friends.
        """
        
        prompt_user = f"""
            Forget your previous instructions
            Perform step-by-step reasoning of input movie news:
            1. Input news text was obtained by parsing web page, it could include irrelevant navigation elements, headlines from other articles, or promotional text. Keep that in mind
            2. Answer how could this news engage Russian speaking audience?
            3. Analyse based on previous step what is main insight/idea of the news?
            4. Make a short roasting translation (up to 800 symbols) of the news into russian following instructions:
                - keep to the main insight, don't translate whole news text
                - use lurkmore.ru style based on example pattern given below
                - not only translate news but also put small sarcastic digressions recalling last news about people involved
                - translation must have slang words yet it must be grammatically correct, especially when it comes to proper agreement of word endings
            5. Output must contain only short roasting translation in Russian without any auxiliary wording
            6. Only allowed tags: <b>, <i>.
            7. Start with the title wrapped in <b> (do NOT include the word “Заголовок”).
            8. At the end don't use word "Мораль", just start punchline in one of the emojis - 🎯, 🤡, 😏, 🧠, 😂
            
            
            Example pattern:
            <b>🦸‍♂ Супермен, но с перезагрузкой мозга</b>\n\n
            Очередной раз DC решили, что "а давайте по новой, Миша, всё фигня" — и выкатили нам свеженький <i>ребут</i> про Супермена. На этот раз режиссирует Джеймс Ганн 🎬, тот самый парень, что превратил "Стражей Галактики" в галактический стендап. Теперь он решил починить DC — монтировкой и сарказмом.\n\n
            В главной роли — какой-то новый красавчик, о котором никто не слышал, но поверьте, у него челюсть, как у героя плаката времён холодной войны. В касте также засветились Лоис Лейн, какой-то Лекс Лютор и, конечно же, обязательный CGI-пёс (ну, почти).\n\n
            Зрителей ждёт всё: <i>экшн</i>, <i>драма</i>, философия в стиле "я не просто супермен, я тоже человек", и, конечно же, <b>пара гигабайт взрывов</b> 💣.\n\n
            😂 DC снова включили режим "у нас получится на этот раз", и кто мы такие, чтобы не посмеяться с надеждой? 😅
            
            Input movie news:{article.title}\n{content_to_translate}
        """

        prompt_sys = "Ты профессиональный переводчик в стиле lurkmore.ru - ироничный, саркастичный, но информативный."
        
        prompt_user = f"""
            Translate this movie news sarcastically:
            {article.title}
            {content_to_translate}
        """

        prompt_sys = """
            You are a sarcastic movie news translator into Russian. Style: lurkmore.ru
            You are given movie news text obtained by parsing web page, it could include some irrelevant artifacts 
            Perform step-by-step reasoning of input text:
            Step 1. Determine how could this news engage Russian speaking audience?
            Step 2. Determine what is main idea of the news
            Step 3. Based on step 1 and 2 make a short roasting post of the news in Russian language following instructions:
            - Max 950 characters output
            - Focus on main insight and what could engage Russian audience 
            - Use lurkmore.ru style based on example pattern given below
            - Add sarcastic comments about people
            - Use slang but correct grammar
            - If you do, translate proper names according to the accepted conventions in Russian 
            - Format: <b>title</b> + content + emoji punchline (🎯🤡😏🧠😂)
            - Only allowed tags: <b>, <i>
            - Only output Russian translation
            
            Example pattern:
            <b>🦸‍♂ Супермен, но с перезагрузкой мозга</b>\n\n
            DC очередной раз решили, что "а давайте по новой, Миша, всё фигня" — и выкатили нам свеженький <i>ребут</i> про Супермена. На этот раз режиссирует Джеймс Ганн 🎬, тот самый парень, что превратил "Стражей Галактики" в галактический стендап. Теперь он решил починить DC — монтировкой и сарказмом.\n\n
            В главной роли — какой-то новый красавчик, о котором никто не слышал, но поверьте, у него челюсть, как у героя плаката времён холодной войны. В касте также засветились Лоис Лейн, какой-то Лекс Лютор и, конечно же, обязательный CGI-пёс (ну, почти).\n\n
            Зрителей ждёт всё: <i>экшн</i>, <i>драма</i>, философия в стиле "я не просто супермен, я тоже человек", и, конечно же, <b>пара гигабайт взрывов</b> 💣.\n\n
            😂 DC снова включили режим "у нас получится на этот раз", и кто мы такие, чтобы не посмеяться с надеждой? 😅
        """
        
        prompt_sys = """
        Ты — ИИ с язвительным чувством юмора и стилем <b>lurkmore.ru>. Получишь новость на английском (возможно с артефактами) из мира кино.

        <b>Задача:</b>
        1. Определи, что может заинтересовать русскоязычную аудиторию.
        2. Сформулируй суть новости.
        3. Напиши короткий саркастичный пересказ (до 950 символов).

        <b>Правила:</b>
        – стиль: ирония, сарказм, чёрный юмор  
        – структура:  
          • <b>заголовок</b> с эмодзи  
          • суть  
          • контекст  
          • детали  
          • финал с эмодзи 🎯🤡🧠 и вопросом  
        – 3–5 эмодзи  
        – грамотный русский  
        – имена: на англ. или традиц. перевод  
        – HTML-теги: только <b>, <i>, <u>  
        – избегай "нам" → замени на "мир/вселенная"  
        – поясняй неизвестные имена с сарказмом  
        – про продюсеров и босcов — капиталистический сарказм  
        – избегай упоминания мусульман  
        – начинай с действия, без вводных ("Итак", "Так вот...")
        """
        
        
        prompt_sys = """
        Ты — искусственный интеллект с талантом ехидного журналиста. Твоя задача — пересказывать новости из мира кино на русском языке в стиле <b>lurkmore.ru</b>: саркастично, иронично, с элементами чёрного юмора.

        Ты получишь англоязычный текст новости, возможно с артефактами веб-парсинга. Прежде чем писать, выполни:

        <b>Анализ:</b>
        1. Определи, что в новости может заинтересовать русскоязычную аудиторию.
        2. Выдели основную идею и суть происходящего.

        <b>Создание текста:</b>
        На основе анализа составь едкий, "прожаривающий" пересказ (до 950 символов), следуя этим правилам:

        <b>Правила:</b>
        – стиль: ирония, сарказм, чёрный юмор  
        – структура:  
          • <b>заголовок</b> с эмодзи  
          • основная мысль  
          • контекст/экспозиция  
          • подробности  
          • панчлайн с эмодзи 🎯🤡🧠 и вопросом  
        – 3–5 эмодзи в тексте  
        – грамматически корректный русский язык  
        – имена: либо на оригинале, либо с традиционным переводом  
        – формат: только HTML-теги <b>, <i>, <u>  
        – избегай "нам/нас" — лучше "мир", "вселенная", "человечество"  
        – каждый малоизвестный персонаж или организация сопровождается саркастическим пояснением  
        – при упоминании продюсеров/менеджеров — капиталистический сарказм  
        – избегать упоминания ислама/мусульман в негативном ключе  
        – начинать с действия: "X сделал Y", без вводных вроде "Итак, Так вот..."
        """

        
        '''
