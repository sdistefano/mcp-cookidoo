import textwrap

from cookidoo_service import CookidooService


SAMPLE_HTML = textwrap.dedent(
    '''
    <core-tiles-list class="core-tiles-list--narrow">
        <core-tile
          id="cr-01KBHZPGSKAHAJATWQR23PWYM8"
          >
          <a href="/created-recipes/fr-FR/01KBHZPGSKAHAJATWQR23PWYM8">
            <!-- Image -->
            <div class="core-tile__image-wrapper">
                <img class="core-tile__image"
                  src="https://patternlib-all.prod.external.eu-tm-prod.vorwerk-digital.com/recipe_image_placeholder-7b4049cfb86f7f29176f93fc6dead4f8.svg"
                  alt="test" />

              <!-- User section -->
              <div class="core-tile__user-section">
                <core-user-avatar>
      <img class="core-user-avatar__img" src="https://patternlib-all.prod.external.eu-tm-prod.vorwerk-digital.com/avatar-41be05ccf2c3301db776c864177224a5.svg " aria-hidden="true"/>
    </core-user-avatar>
              </div>

              <!-- Public label -->
            </div>

            <div class="core-tile__description-wrapper">
              <!-- Description -->
              <div class="core-tile__description">
                <core-ellipsis>
                  <p class="core-tile__description-text"> test </p>
                </core-ellipsis>
              </div>

              <!-- Context menu button -->
                <button class="core-tile__trigger context-menu-trigger" aria-label="open context menu" type="button"></button>
            </div>
          </a>

          <core-context-menu trigger-class="context-menu-trigger">
      <ul class="core-dropdown-list">
          <li><core-transclude href="/planning/fr-FR/transclude/manage-cook-today/01KBHZPGSKAHAJATWQR23PWYM8?recipeSource&#x3D;CUSTOMER" prevent-page-reload="true" on="context-menu-open" context="core-context-menu">
    </core-transclude>
    </li>
          <li><core-transclude href="/planning/fr-FR/transclude/manage-add-to-myweek/01KBHZPGSKAHAJATWQR23PWYM8?recipeSource&#x3D;CUSTOMER" prevent-page-reload="true" on="context-menu-open" context="core-context-menu">
    </core-transclude>
    </li>
          <li><core-transclude
        href="/shopping/fr-FR/partial/add-to-shopping-list/01KBHZPGSKAHAJATWQR23PWYM8?source&#x3D;CUSTOMER"
        prevent-page-reload="true"
        on="context-menu-open"
        context="core-context-menu">
    </core-transclude>
    </li>
          <li><a class="core-dropdown-list__item" href="/created-recipes/fr-FR/01KBHZPGSKAHAJATWQR23PWYM8/edit">
      <span class="icon icon--edit-pen" aria-hidden="true"></span>
      Modifier la recette
    </a>
    </li>
          <li><cr-share-trigger
      recipe-id="01KBHZPGSKAHAJATWQR23PWYM8"
      recipe-name="test"
      recipe-image-template=""
      
      work-status="PRIVATE"
      show-links>
      <button class="core-dropdown-list__item">
        <span class="icon icon--share-generic" aria-hidden="true"></span>
        Partager la recette
      </button>
    </cr-share-trigger>
    </li>
          <li><button id="delete-button-01KBHZPGSKAHAJATWQR23PWYM8" class="core-dropdown-list__item core-dropdown-list__item--destructive">
      <span class="icon icon--delete" aria-hidden="true"></span>
      Supprimer la recette
    </button>
    </li>
      </ul>
    </core-context-menu>
    </core-tile>
    </core-tiles-list>
    '''
)


def test_parse_custom_recipes_html_single_tile():
    base_url = "https://cookidoo.fr"
    recipes = CookidooService._parse_custom_recipes_html(SAMPLE_HTML, base_url)

    assert len(recipes) == 1
    recipe = recipes[0]

    assert recipe["id"] == "01KBHZPGSKAHAJATWQR23PWYM8"
    assert recipe["name"] == "test"
    assert recipe["url"] == (
        "https://cookidoo.fr/created-recipes/fr-FR/01KBHZPGSKAHAJATWQR23PWYM8"
    )
