# Rich HTML: грамматика и лимиты

Сверено с официальной документацией Telegram Bot API (core.telegram.org/bots/api) для Bot API 10.3. API развивается — перед продом сверяйся с официальной страницей.

## Модель ввода

`InputRichMessage` принимает ровно одно поле контента: `html`, `markdown` или `blocks`. Дополнительно: `media` (файлы для tg://-ссылок), `is_rtl`, `skip_entity_detection`. Для агентских постов предсказуемее всего Rich HTML + явный массив `media` — этот путь и использует `publish_rich.py` (aiogram ≥ 3.31).

## Лимиты

| Параметр | Лимит |
|---|---|
| Текст | 32 768 символов UTF-8 |
| Блоки (включая вложенные) | 500 |
| Вложенность | 16 уровней |
| Медиа | 50 |
| Колонки таблицы | 20 |

`validate_rich.py` проверяет всё это офлайн по явному allowlist: неизвестные теги, лишние атрибуты, обработчики событий, inline-стили, опасные схемы URL, битую вложенность и медиа-инвариант.

## Инлайн-разметка

```html
<b>жирный</b> <i>курсив</i> <u>подчёркнутый</u> <s>зачёркнутый</s>
<code>код</code> <mark>выделение</mark> <sub>нижний</sub> <sup>верхний</sup>
<tg-spoiler>спойлер</tg-spoiler> <tg-math>x^2</tg-math>
<a href="https://example.com">ссылка</a>
```

## Блоки

```html
<h2>Заголовок раздела</h2>
<p>Абзац.</p>
<hr/>

<ul>
  <li>Пункт</li>
  <li><input type="checkbox" checked/> Выполненный пункт</li>
</ul>

<blockquote>Цитата<cite>Источник</cite></blockquote>
<aside>Ключевой вывод<cite>Примечание</cite></aside>

<details>
  <summary>Раскрыть подробности</summary>
  <p>Дополнительный контекст.</p>
</details>

<table bordered striped>
  <caption>Сравнение</caption>
  <tr><th>Вариант</th><th>Когда</th></tr>
  <tr><td>Альбом</td><td>Совместимость важнее</td></tr>
</table>

<footer>Источник и кредиты</footer>
```

Также документированы: код-блоки, формулы (`tg-math-block`), якоря, сноски (`tg-reference`), карты (`tg-map`), коллажи, слайдшоу, кнопки (`tg-button`).

## Медиа

```html
<img src="tg://photo?id=cover"/>
<video src="tg://video?id=demo"></video>
<audio src="tg://audio?id=episode"></audio>
<tg-document src="tg://document?id=guide"></tg-document>
```

Каждый ID объявляется в массиве `media`. ID: `[A-Za-z0-9_-]{1,64}`. Локальный файл передаётся как файл (в aiogram — `FSInputFile`), публичный HTTPS-URL — строкой. Медиа-элементы стоят отдельными блоками, вне абзацев.

## Слайдшоу и коллаж

```html
<tg-slideshow>
  <img src="tg://photo?id=p1"/>
  <img src="tg://photo?id=p2"/>
  <figcaption>Одна подпись на слайдшоу<cite>Автор фото</cite></figcaption>
</tg-slideshow>

<tg-collage>
  <img src="tg://photo?id=p1"/>
  <img src="tg://photo?id=p2"/>
</tg-collage>
```

## Сноски и якоря

```html
<p>Утверждение со сноской<a href="#note-1">[1]</a>.</p>
<tg-reference name="note-1">Описание источника и URL.</tg-reference>
```

Пустой `<a name="section"></a>` отдельной строкой создаёт внутренний якорь.

## HTML-сущности

Числовые — все; именованные — ограниченный документированный набор: `&lt; &gt; &amp; &quot; &apos; &nbsp; &hellip; &mdash; &ndash; &lsquo; &rsquo; &ldquo; &rdquo;`. Надёжнее писать пунктуацию литералами UTF-8.

## Совместимость

Старые клиенты показывают Rich Message как «неподдерживаемое сообщение». Для широкой аудитории всегда готовь fallback: обычный пост или альбом (`publish_fallback.py`). История версий: Rich Messages появились в Bot API 10.1, массив `media` и input-блоки — в 10.2, документы и дополнительные контролы — в 10.3.
