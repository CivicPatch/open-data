require_relative "../../scrapers/city_directory"
module CityScrape
  class SearchManager
    def self.fetch_search_results(engine, state, city_entry)
      city = city_entry["name"]
      website = city_entry["website"]
      urls = []
      keyword_groups = Scrapers::CityDirectory::MAYOR_COUNCIL_KEYWORDS

      avoid_keywords = %w[alerts news event calendar]

      case engine
      when "manual"
        # TODO: replace with actual keyword groups
        urls += Crawler.crawl(website, keyword_groups: keyword_groups, avoid_keywords: avoid_keywords)
      when "brave"
        keyword_groups.map do |group|
          search_query = "#{city} #{state} #{group[:name]}"
          urls += Services::Brave.get_search_result_urls(search_query, website)
        end
      end

      filtered_urls = Scrapers::Common.urls_without_keywords(urls, %w[alerts news event calendar])
      puts "Filtered out #{urls.size - filtered_urls.size} urls"
      filtered_urls.map { |url, _text| url }
    end
  end
end
